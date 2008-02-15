#!/usr/bin/env python
#
# a test client for rserver 
#

from xmlrpclib import ServerProxy, Error
import sys

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
	print "\t[", var_str, "variable_string]"
	print "\t[", qtext_str, "questiontext_string]"
	print "\t[", ans_str, "answer_string]"
	print "\t[", aid_str, "answerid]"
	print "\t[", tol_str, "tolerance_string]"
	print "Note: While all the components are optional, invoking without any"
	print "      is a rather silly thing to do."
	print "Note: answer, tolerance and ansid may be repeated many times"
	print "      each is processed in the order passed independently"

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
		
#######################################################################
if len(sys.argv) < 2:
	# this is no good
	print "Need command line options!"
	print_usage()
	sys.exit(1)

if len(sys.argv[1:]) % 2 != 0:
	print "Need an even number of command line options!"
	print_usage()
	sys.exit(1)

(server, question) = get_question(sys.argv[1:])
resp = send_question(server, question)
print resp
