#!/usr/bin/env python
#
# a test client for rserver 
#

from xmlrpclib import ServerProxy, Error
import xml.dom.minidom 
import sys

help_str  = "--help"
xml_str   = "--xml"
url_str   = "--url"
qtext_str = "--questiontext"
var_str   = "--variables"
ans_str   = "--answer"
tol_str   = "--tolerance"
aid_str   = "--ansid"
#######################################################################
def print_usage():
	print sys.argv[0]
	print "\t", url_str, "server_url"
	print "\t[", help_str, "] print this help msg"
	print "\t[", xml_str, "xmlfile] process an xml file of questions"
	print "\t[", var_str, "variable_string]"
	print "\t[", qtext_str, "questiontext_string]"
	print "\t[", ans_str, "answer_string]"
	print "\t[", aid_str, "answerid]"
	print "\t[", tol_str, "tolerance_string]"
	print "Note: While all the components are optional, invoking without any"
	print "      is a rather silly thing to do."
	print "Note: answer, tolerance and ansid may be repeated many times"
	print "      each is processed in the order passed independently"
	print "Note: an xmlfile may contain as many questions as you like, they"
	print "      will be processed sequentially"

#######################################################################
def get_question(args):
	# we don't need to worry about even length, it will be checked before we
	# are called
	# blank question to return, we will fill it as we go
	question = {'questiontext': "", 'variables': "", 'answers': []}
	server   = ""
	# these keep the answer components in the right place
	ans_idx = tol_idx = ans_idx = 0
	idx = 0
	while(idx < len(args)):
		option = args[idx]
		value  = args[idx+1]
		if option == url_str: 
			server = value
		elif option == qtext_str: 
			question['questiontext'] = value
		elif option == var_str: 
			question['variables'] = value
		elif option == ans_str or option == tol_str or option == aid_str:
			# these are a little more complicated
			if option == ans_str: a_idx = ans_idx
			elif option == tol_str: a_idx = tol_idx
			else: a_idx = aid_idx
			while(len(question['answers']) < (a_idx + 1)):
				question['answers'].append({'ansid': 0, 'answer': "", 'tolerance': ""})
			if option == ans_str:
				question['answers'][ans_idx]['answer'] = value
				ans_idx = ans_idx + 1
			if option == tol_str:
				question['answers'][tol_idx]['tolerance'] = value
				tol_idx = tol_idx + 1
			if option == aid_str:
				question['answers'][aid_idx]['ansid'] = value
				aid_idx = aid_idx + 1
		else:
			## unknown option
			print option, "is not recognized"
			print_usage()
			sys.exit(1)
		idx = idx + 2
	return (server, question)
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
	qxml.setAttribute("type", "ltjprocesed")
	for key in ['name', 'variables', 'questiontext', 'numanswers']:
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
	questions    = []
	question     = {}
	question['answers'] = []
	server       = ""
	xml_file     = ""
	
	xml_found    = False
	cl_found     = False
	idx = 0
	ans_idx = 0
	tol_idx = 0
	aid_idx = 0
	while(idx < len(args)):
		option = args[idx]
		value  = args[idx+1]
		if option == url_str:
			server = value
		elif option == xml_str:
			if xml_file != "":
				print "Can only handle 1 xml file at a time"
				sys.exit(1)
			xml_file = value
			xml_found = True
		elif option == qtext_str: 
			question['questiontext'] = value
			cl_found = True
		elif option == var_str: 
			question['variables'] = value
			cl_found = True
		elif option == ans_str or option == tol_str or option == aid_str:
			cl_found = True
			# these are a little more complicated
			if option == ans_str: a_idx = ans_idx
			elif option == tol_str: a_idx = tol_idx
			else: a_idx = aid_idx
			while(len(question['answers']) < (a_idx + 1)):
				question['answers'].append({'ansid': 0, 'answer': "", 'tolerance': ""})
			if option == ans_str:
				question['answers'][ans_idx]['answer'] = value
				ans_idx = ans_idx + 1
			if option == tol_str:
				question['answers'][tol_idx]['tolerance'] = value
				tol_idx = tol_idx + 1
			if option == aid_str:
				question['answers'][aid_idx]['ansid'] = value
				aid_idx = aid_idx + 1
		else:
			## unknown option
			print option, "is not recognized"
			print_usage()
			sys.exit(1)
		idx = idx + 2
			

	if xml_found and cl_found:
		print "Can't mix command line and xml questions"
		sys.exit(1)

	if xml_found:
		questions = read_xml_file(xml_file)
	elif cl_found:
		questions.append(question)
	
	return process_questions(server, questions)
#######################################################################
def read_xml_file(xml_file):
	questions = []
	xmldata = xml.dom.minidom.parse(xml_file)
	rootnode = xmldata.childNodes[0]
	for node in rootnode.childNodes:
		if node.localName == 'question':
			if node.getAttribute("type") == "ltjprocessed":
				questions.append(process_qnode(node))
	return questions
				
	
#######################################################################
## this xml indexing seems a little obtuse, this probably means I'm doing it wrong
def process_qnode(qnode):
	question = {}
	ltjnode = None
	for node in qnode.childNodes:
		if node.localName == "name":
			question['name'] = node.childNodes[1].childNodes[0].nodeValue
		elif node.localName == "questiontext":
			question['questiontext'] = node.childNodes[1].childNodes[0].nodeValue
		elif node.localName == "ltjprocessed":
			ltjnode = node
	ansnd = None
	if ltjnode != None:
		for node in ltjnode.childNodes:
			if node.localName == 'variables':
				question['variables'] = node.childNodes[0].nodeValue
			elif node.localName == 'answers':
				ansnd = node
		
	answers = []
	for nd in ansnd.childNodes:
		if nd.localName == 'answer':
			ans = {}
			for nd1 in nd.childNodes:
				if nd1.localName != None:
					ans[nd1.localName] = nd1.childNodes[0].nodeValue
			answers.append(ans)
	question['answers'] = answers
	return question
				
	
#######################################################################
if len(sys.argv) < 2:
	# this is no good
	print "Need command line options!"
	print_usage()
	sys.exit(1)

if len(sys.argv[1:]) == 1 and sys.argv[1] == help_str:
	print_usage()
	sys.exit(0)
	
if len(sys.argv[1:]) % 2 != 0:
	print "Need an even number of command line options!"
	print_usage()
	sys.exit(1)

process_command_line(sys.argv[1:])

sys.exit(0)
