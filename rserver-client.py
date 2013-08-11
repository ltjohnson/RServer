#!/usr/bin/env python
#
# a test client for rserver 
#

import argparse
from xmlrpclib import ServerProxy, Error
import xml.dom.minidom 
import sys

parser = argparse.ArgumentParser(description='Send xml requests to an RServer.')
parser.add_argument('--xmlfile', dest='xmlfile', type=str, nargs=1, 
    help='process a xml file of questions.')
parser.add_argument('--url', dest='serverurl', type=str, 
    help='server url to send requests to.', nargs=1, required=True)
parser.add_argument('--variables', dest='variables', type=str, nargs=1, 
    help='variables string to send to server.')
parser.add_argument('--questiontext', dest='questiontext', type=str, nargs=1, 
    help='questiontext string to send to server.')
parser.add_argument('--answer', dest='answer', type=str, nargs='+', 
    help='answer string to send to server.')
parser.add_argument('--answerid', dest='ansid', type=int,
    help='answer id to send to server.', nargs='+')
parser.add_argument('--tolerance', dest='tolerance', type=str,
    help='tolerance string to send to server.', nargs='+')

#######################################################################
def send_question(url, question):
	server = ServerProxy(url)
	try:
		resp = server.processquestion(question)
	except Error, v:
		resp = v
	return resp

def process_questions(server, questions):
	for question in questions:
		resp = send_question(server, question)
		xml = convert_question_toxml(resp)
		print xml.toprettyxml("  ")
#######################################################################
def convert_question_toxml(question):
	doc = xml.dom.minidom.Document()
	qxml = doc.createElement("question")
	qxml.setAttribute("type", "remoteprocessed")
	for key in ['name','variables', 'questiontext', 'numanswers']:
		if question.has_key(key):
			ml = doc.createElement(key)
			ml.appendChild(doc.createTextNode(str(question[key])))
			qxml.appendChild(ml)
	if question.has_key('answers'):
		answers = doc.createElement("answers")
		for ans in question['answers']:
			ansnd = doc.createElement("answer")
			for key in ans.keys():
				ml = doc.createElement(key)
				ml.appendChild(doc.createTextNode(str(ans[key])))
				ansnd.appendChild(ml)
			answers.appendChild(ansnd)
		qxml.appendChild(answers)
				
	return qxml
#######################################################################
def process_command_line(args):
	parsed_args = parser.parse_args(args)
	args_dict = vars(parsed_args)
	args_dict = dict((k, v) for k, v in args_dict.items() if v is not None)
	args_keys = set(args_dict.keys()).difference(set("serverurl"))
	if 'xmlfile' in args_dict and len(args_dict) > 1:
		print "You may not specifiy xmlfile with any other options"
		sys.exit(0)
	return args_dict


def read_xml_options(args):
	question = dict()
	for key in ['questiontext', 'variables']:
		if key in args:
			question[key] = args[key][0]

	# Goal: build the repeatable answer fields into a list of dictionaries.
	#       What comes in is args['ansid'] = ansid_list, 
	#       args['answer'] = answer_list, and 
	#       args['tolerance'] = tolerance_list.  We want to convert this to
	#       a list of dictionaries, having the form:
	#         [{'answer': answer_list[0], 'tolerance': tolerance_list[0], 
	#           'ansid': ansid_list[0]}, ...]
	#       There is probably a better python way of doing this.
	# Find the longest of the repeatable answer fields.
	question['answers'] = []
	answer_keys = [
		x for x in ['ansid', 'answer', 'tolerance'] if x in args.keys()]
	if len(answer_keys) == 0:
		return [question]

	answer_dict_lists = [[{key: v} for v in args[key]] for key in answer_keys]
	numanswers = max(len(l) for l in answer_dict_lists)

	for i in xrange(len(answer_dict_lists)):
		for j in xrange(len(answer_dict_lists[i]), numanswers):
			answer_dict_lists[i].append(dict())

	for i in xrange(numanswers):
		question['answers'].append(dict())
		for j in xrange(len(answer_dict_lists)):
			question['answers'][i].update(answer_dict_lists[j][i])

	return [question]

#######################################################################
def read_xml_file(xml_file):
	questions = []
	xmldata = xml.dom.minidom.parse(xml_file)
	rootnode = xmldata.childNodes[0]
	for node in rootnode.childNodes:
		if node.localName == 'question':
			if node.getAttribute("type") == "remoteprocessed":
				questions.append(process_qnode(node))
	return questions
				
	
#######################################################################
## this xml indexing seems a little obtuse, this probably means I'm doing it wrong
def process_qnode(qnode):
	question = {}
	remote_node = None
	for node in qnode.childNodes:
		if node.localName == "name":
			question['name'] = node.childNodes[1].childNodes[0].nodeValue
		elif node.localName == "questiontext":
			question['questiontext'] = node.childNodes[1].childNodes[0].nodeValue
		elif node.localName == "remoteprocessed":
			remote_node = node
	ansnd = None
	if remote_node != None:
		for node in remote_node.childNodes:
			if node.localName == 'variables':
				question['variables'] = node.childNodes[0].nodeValue
			elif node.localName == 'answers':
				ansnd = node
		
	answers = []
	for nd in ansnd.childNodes:
		if nd.localName == 'answer':
			ans = dict((nd1.localeName, nd1.childNodes[0].nodeValue) for
				nd1 in nd.childNodes if nd1.localName is not None)
			answers.append(ans)
	question['answers'] = answers
	return question
				
	
#######################################################################
if __name__ == "__main__":
	command_options = process_command_line(sys.argv[1:])
	if 'xmlfile' in command_options:
		questionxml_list = read_xml_file(command_options['xmlfile'][0])
	else:
		questionxml_list = read_xml_options(command_options)
	process_questions(command_options['serverurl'][0], questionxml_list)
