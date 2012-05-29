#!/usr/bin/env python
# Read a file in "sections.txt" and produce "sections.json" which is a distillation of ad sections
# "sections.txt" can be copy/pasted out of 
# http://content.p2p.edge.tribuneinteractive.com/product_affiliate_sections?id=366
# and this will ignore the junk and produce a json file which is just an array of section paths
import json, os.path
CURRENT_DIR = os.path.dirname(__file__)
PREFIXES = ['/news', '/sports', '/business', '/entertainment', '/features', '/health', '/travel', '/classified']
sections = []
for line in map(str.rstrip,open(os.path.join(CURRENT_DIR,"sections.txt"))):
    for start in PREFIXES:
        if line.startswith(start):
            sections.append(line)

sections.sort()
json.dump(sections,open(os.path.join(CURRENT_DIR,'sections.json'),"w"))
print "Done: %i sections" % (len(sections))

