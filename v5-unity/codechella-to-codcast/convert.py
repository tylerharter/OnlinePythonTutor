# this script converts a codechella session log recorded by
# ../../v3/opt_togetherjs/server.js
#
# and turns it into the codcast format, which is readable by
# ../js/recorder.ts and ../js/demovideo.ts

# created: 2018-05-27

# HUGE WARNING: DO NOT RUN THIS ON UNTRUSTED CODE YET, SINCE IT WILL
# SIMPLY EXECUTE THE CODE VERBATIM TO GENERATE TRACES FOR THE CACHE; IF
# THE CODE IS MALICIOUS, THEN IT WILL POSSIBLY HARM YOUR COMPUTER!!!

'''

NB: now that i think about it more, it's not entirely clear to me
whether you can always tell who initiated an app.editCode event with any
kind of certainty. oh wells, throw up our hands for nows.

NB: one big challenge is that some types of events are duplicated (or
repeated N times if there are N people in the session) since TogetherJS
logs everyone's actions separately
- app.editCode events are DEFINITELY duplicated

TODOs:
- not sure how much hashchange events matter

'''

from collections import defaultdict
import dateutil.parser
import json
import os
import sys
import time

print >> sys.stderr, 'WARNING: do not run this on a trace containing untrusted code'

# somewhat modeled after ../js/demovideo.ts
ALL_LEGIT_TYPES = (
    'app.initialAppState',
    'hello',
    'peer-update',
    'form-update',
    'cursor-update',
    'chat',
    'app.editCode',
    'app.executeCode',
    'app.updateOutput',
    'app.aceChangeCursor',
    'app.aceChangeSelection',
    'pyCodeOutputDivScroll',
    'app.hashchange',
)

# TODO: maybe we don't need this since TogetherJS will take care of
# mapping clientId's to usernames for us ...
#
# Key: clientId, Value: current username (might change throughout the
# session; keep the latest one)
clientIdtoUsername = {}

firstInitialAppState = None
firstClientId = None
raw_events = []

# Key: delta 'd' field, value: list of code edit events with that same 'd'
#
# NB: this won't be fully accurate if there are several *independent*
# sets of edits occurring at vastly different times which have the same 'd'
all_code_edits_by_deltas = defaultdict(list)

for line in open(sys.argv[1]):
    rec = json.loads(line)
    if rec['type'] != 'togetherjs':
        continue
    
    tjs = rec['togetherjs']
    typ = tjs['type']
    if typ not in ALL_LEGIT_TYPES:
        continue

    # read only the FIRST initialAppState since we'll assume that's who
    # initiated the session
    if not firstInitialAppState and typ == 'app.initialAppState':
        firstInitialAppState = rec
        firstClientId = tjs['clientId']

    # don't append any initialAppState events:
    if typ == 'app.initialAppState':
        continue

    if typ == 'app.editCode':
        all_code_edits_by_deltas[tjs['delta']['d']].append(tjs)

    # it's really tricky to log editCode events since they often appear as
    # duplicates (or even more copies if there are more people in the session).
    # the easiest way to manage it is to record only editCode events belonging
    # to the firstClientId user and discard all other ones.
    if typ == 'app.editCode' and firstClientId and tjs['clientId'] != firstClientId:
        continue

    raw_events.append(rec)


#        if tjs['delta']['d'] == lastEditCodeEvent['togetherjs']['delta']['d']:
#            assert tjs['delta']['t'] >= lastEditCodeEvent['togetherjs']['delta']['t']
#            continue # get outta here!

events = []

for e in raw_events:
    tjs = e['togetherjs']

    # clean up and append to final events
    dt = dateutil.parser.parse(e['date'])
    # get timestamp in milliseconds
    ms = int(time.mktime(dt.timetuple())) * 1000

    # for app.codeEdit events, look up who the ORIGINAL PERSON was who
    # initiated this edit event, and log their clientId, which may be
    # different than your own clientId
    if tjs['type'] == 'app.editCode':
        d = tjs['delta']['d']
        t = tjs['delta']['t']
        assert d in all_code_edits_by_deltas
        firstEdit = all_code_edits_by_deltas[d][0]
        firstEditTimestamp = firstEdit['delta']['t']
        # sanity check: note that this will fail if we have multiple
        # identical sets of edits that take place at vastly
        # different points in time, but let's cross that bridge when
        # we get to it
        assert firstEditTimestamp <= t
        assert t - firstEditTimestamp < 5000 # give it a 5-second buffer for sanity checking

        tjs['clientId'] = firstEdit['clientId'] # change the clientId for this event!


    # add these fields to match codcast format
    tjs['ts'] = ms
    tjs['sameUrl'] = True
    tjs['peer'] = {'color': '#8d549f'} # not sure if this is necessary
    # TODO: we need to add frameNum field later on; or maybe just add it here?!?

    events.append(tjs)


for e in events:
    print json.dumps(e)
