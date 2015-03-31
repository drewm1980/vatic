import os.path, sys, cgi, shutil
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import tempfile
from tracking import run_tracking
from tracking_helpers import convert_track_to_path
from turkic.server import handler, application
from turkic.database import session
import cStringIO
from models import *
import numpy as np
import os

import logging
logger = logging.getLogger("vatic.server")

HOMOGRAPHY_DIR = "homography"

@handler()
def getjob(id, verified):
    job = session.query(Job).get(id)

    logger.debug("Found job {0}".format(job.id))

    if int(verified) and job.segment.video.trainwith:
        # swap segment with the training segment
        training = True
        segment = job.segment.video.trainwith.segments[0]
        logger.debug("Swapping actual segment with training segment")
    else:
        training = False
        segment = job.segment

    video = segment.video
    labels = dict((l.id, l.text) for l in video.labels)

    attributes = {}
    for label in video.labels:
        attributes[label.id] = dict((a.id, a.text) for a in label.attributes)

    logger.debug("Giving user frames {0} to {1} of {2}".format(video.slug,
                                                               segment.start,
                                                               segment.stop))

    homography = video.gethomography()
    if homography is not None:
        homography = homography.tolist()

    return {"start":        segment.start,
            "stop":         segment.stop,
            "slug":         video.slug,
            "width":        video.width,
            "height":       video.height,
            "skip":         video.skip,
            "perobject":    video.perobjectbonus,
            "completion":   video.completionbonus,
            "blowradius":   video.blowradius,
            "jobid":        job.id,
            "training":     int(training),
            "labels":       labels,
            "attributes":   attributes,
            "homography":   homography}

@handler()
def getboxesforjob(id):
    job = session.query(Job).get(id)
    result = []
    for path in job.paths:
        attrs = [(x.attributeid, x.frame, x.value) for x in path.attributes]
        result.append({"label": path.labelid,
                       "boxes": [tuple(x) for x in path.getboxes()],
                       "attributes": attrs})
    return result

def readpath(label, track, attributes):
    path = Path()
    path.label = session.query(Label).get(label)
 
    logger.debug("Received a {0} track".format(path.label.text))

    visible = False
    for frame, userbox in track.items():
        box = Box(path = path)
        box.xtl = max(int(userbox[0]), 0)
        box.ytl = max(int(userbox[1]), 0)
        box.xbr = max(int(userbox[2]), 0)
        box.ybr = max(int(userbox[3]), 0)
        box.occluded = int(userbox[4])
        box.outside = int(userbox[5])
        box.generated = int(userbox[6])
        box.frame = int(frame)
        if not box.outside:
            visible = True

        logger.debug("Received box {0}".format(str(box.getbox())))

    if not visible:
        logger.warning("Received empty path! Skipping")
        return

    for attributeid, timeline in attributes.items():
        attribute = session.query(Attribute).get(attributeid)
        for frame, value in timeline.items():
            aa = AttributeAnnotation()
            aa.attribute = attribute
            aa.frame = frame
            aa.value = value
            path.attributes.append(aa)
    return path

def readpaths(tracks):
    paths = []
    logger.debug("Reading {0} total tracks".format(len(tracks)))
    return [readpath(label, track, attributes) for label, track, attributes in tracks]

@handler(post = "json")
def savejob(id, tracks):
    job = session.query(Job).get(id)

    for path in job.paths:
        session.delete(path)
    session.commit()

    for path in readpaths(tracks):
        logger.info(path)
        job.paths.append(path)
    session.add(job)
    session.commit()

@handler(post = "json")
def validatejob(id, tracks):
    job = session.query(Job).get(id)
    paths = readpaths(tracks)

    return job.trainingjob.validator(paths, job.trainingjob.paths)

@handler()
def respawnjob(id):
    job = session.query(Job).get(id)

    replacement = job.markastraining()
    job.worker.verified = True
    session.add(job)
    session.add(replacement)
    session.commit()

    replacement.publish()
    session.add(replacement)
    session.commit()

@handler(post = "json")
def trackfromframe(id, frame, algorithm, position):
    frame = int(frame)
    job = session.query(Job).get(id)
    segment = job.segment
    video = segment.video
    xtl, ytl, xbr, ybr, occluded, outside, generated = position

    logger.info("Job Id: {0}".format(id))
    logger.info("Algorithm: {0}".format(algorithm))

    tracks = run_tracking(frame, segment.stop, video.location, (xtl, ytl, xbr-xtl, ybr-ytl))
    path = convert_track_to_path(frame, tracks, job)
    attrs = [(x.attributeid, x.frame, x.value) for x in path.attributes]

    logger.info("Path: {0}".format(path))

    return {
        "label": 0,
        "boxes": [tuple(x) for x in path.getboxes()],
        "attributes": attrs
    }

@handler(post = "json")
def trackbetweenframes(id, leftframe, rightframe, algorithm, pos):
    leftpos, rightpos = pos
    lxtl, lytl, lxbr, lybr, loccluded, loutside, lgenerated = leftpos
    rxtl, rytl, rxbr, rybr, roccluded, routside, rgenerated = rightpos
    leftframe = int(leftframe)
    rightframe = int(rightframe)

    logger.info("Track from {0} to {1}".format(leftframe, rightframe))
    logger.info("Job Id: {0}".format(id))
    logger.info("Algorithm: {0}".format(algorithm))

    job = session.query(Job).get(id)
    segment = job.segment
    video = segment.video

    #tracks = run_tracking(frame, segment.stop, video.location, (xtl, ytl, xbr-xtl, ybr-ytl))
    #path = convert_track_to_path(frame, tracks, job)
    #attrs = [(x.attributeid, x.frame, x.value) for x in path.attributes]

    return {
        "label": 0,
        "boxes": [],
        #"boxes": [tuple(x) for x in path.getboxes()],
        #"attributes": attrs
        "attributes": []
    }

@handler()
def getallvideos():
    query = session.query(Video)
    videos = []
    for video in query:
        newvideo = {
            "slug": video.slug,
            "segments": [],
        }
        for segment in video.segments:
            newsegment = {
                "start": segment.start,
                "stop":segment.stop,
                "jobs":[],
            }

            for job in segment.jobs:
                newsegment["jobs"].append({
                    "url": job.offlineurl(config.localhost),
                    "numobjects": len(job.paths),
                })

            newvideo["segments"].append(newsegment)

        videos.append(newvideo)
    return videos

@handler()
def getvideo(slug):
    query = session.query(Video).filter(Video.slug == slug)
    if query.count() != 1:
        raise ValueError("Invalid video slug")
    video = query[0]
    homography = video.gethomography()
    if homography is not None:
        homography = homography.tolist()

    return {
        "slug": video.slug,
        "width": video.width,
        "height": video.height,
        "homography":homography,
    }

@handler(post = "json")
def savehomography(slug, homography):
    query = session.query(Video).filter(Video.slug == slug)
    if query.count() != 1:
        raise ValueError("Invalid video slug")
    video = query[0]

    base = video.location
    savedir = os.path.join(base, HOMOGRAPHY_DIR)
    if not os.path.isdir(savedir):
        os.makedirs(savedir)
    savelocation = os.path.join(savedir, "homography.npy")
    np.save(np.array(homography), savelocation)
    video.homographylocation = savelocation
    session.add(video)
    session.commit()

@handler(post = True, environ = True)
def savetopview(slug, image, environ):
    logger.info("Saving topview image")

    query = session.query(Video).filter(Video.slug == slug)
    if query.count() != 1:
        raise ValueError("Invalid video slug")
    video = query[0]

    base = video.location
    savedir = os.path.join(base, HOMOGRAPHY_DIR)
    if not os.path.isdir(savedir):
        os.makedirs(savedir)

    savelocation = os.path.join(savedir, "topview.jpg")
    tempformfile = tempfile.TemporaryFile()
    tempformfile.write(image)
    tempformfile.seek(0)
    form = cgi.FieldStorage(fp=tempformfile, environ=environ, keep_blank_values=True)
    outfile = open(savelocation, "w+b")
    shutil.copyfileobj(form['photo'].file, outfile)
    tempformfile.close()
    outfile.close()


