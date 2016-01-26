"""A command line tool for annotating .hsreplay files with GameTag data to facilitate development activities."""
from xml.etree import ElementTree as ET
import sys, argparse
from hearthstone.enums import *


def _to_string(tag):
	result = "<%s" % tag.tag
	if len(tag.attrib):
		result += " "
		result += " ".join("%s=%s" % item for item in tag.attrib.items())
	result += ">"
	return result


def annotate_replay(infile, outfile, verbose = False):

	tree = ET.parse(infile)
	root = tree.getroot()

	for tag in root.iter('Tag'):
		if verbose:
			print(tag.tag, tag.attrib)

		try:
			name = GameTag(int(tag.attrib['tag'])).name
			tag.set("GameTagName", name)

			if name == "STEP":
				tag.set("StepName", Step(int(tag.attrib['value'])).name)

			if name == "ZONE":
				tag.set("ZoneName", Zone(int(tag.attrib['value'])).name)

		except ValueError:
			print("WARNING: tag %s in Tag '%s' is not a valid GameTag" % (tag.attrib['tag'], _to_string(tag)))

	for tag_change in root.iter('TagChange'):
		if verbose:
			print(tag_change.tag, tag_change.attrib)

		try:
			name = GameTag(int(tag_change.attrib['tag'])).name
			tag_change.set("GameTagName", name)

			if name == "STEP":
				tag_change.set("StepName", Step(int(tag_change.attrib['value'])).name)

			if name == "ZONE":
				tag_change.set("ZoneName", Zone(int(tag_change.attrib['value'])).name)

			if name == "MULLIGAN_STATE":
				tag_change.set("MulliganStateName", Mulligan(int(tag_change.attrib['value'])).name)

		except ValueError:
			print("WARNING: tag %s in TagChange '%s' is not a valid GameTag" % (tag_change.attrib['tag'], _to_string(tag_change)))

	for action in root.iter('Action'):
		if verbose:
			print(action.tag, action.attrib)

		try:
			name = PowSubType(int(action.attrib['type'])).name
			action.set("ActionTypeName", name)
		except ValueError:
			print("WARNING: type %s in Action '%s' is not a valid PowSubType" % (action.attrib['tag'], _to_string(action)))

	tree.write(outfile)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("infile", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="the input replay data")
	parser.add_argument("outfile", nargs='?', type=argparse.FileType('wb'), default=sys.stdout.buffer, help="the annotated replay data")
	parser.add_argument('--verbose', action='store_true', help="print elements to console as they are annotated")

	args = parser.parse_args()
	annotate_replay(args.infile, args.outfile, verbose=args.verbose)

