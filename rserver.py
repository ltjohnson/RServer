#!/usr/bin/python
## it's important to keep this as /usr/bin/env python for cross platform
## compatibility

import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import SimpleXMLRPCServer, base64, time, os

################################################################################
# all of these options are defaults and configurable in the config file
tmpdir   = "/home/ruser/rserver_tmp"
logfile  = "/home/ruser/log/rserver.log"
loglevel = 1

workspacetime = str(int(time.time())%1000)
def R_clean_workspace(): return tmpdir + "/" + workspacetime + ".rda"

host = "localhost"
port = 8080

def build_clean_R(): return ["rm(list=ls(all=TRUE))", "load(\""+R_clean_workspace()+"\")"]
def build_close_R(): return ["rm(list=ls(all=TRUE))"]
def build_grade_R(): return ['library(grade, lib.loc="/home/ruser/R-library")']

clean_R = build_clean_R()
close_R = build_close_R()
grade_R = build_grade_R()
################################################################################
start_time = time.time()
requests   = 0

## logging faclities
def log(msg, level=2):
    if level > loglevel: return None
    logf = open(logfile, "a")
    logf.write(msg)
    logf.close()
    return None

def log_question(question):
    log_str = ""
    if question.has_key('variables'):
	    log_str = log_str + "variables[" + question['variables'].replace("\n", "\\n") + "]\n"
    if question.has_key('questiontext'):
	log_str = log_str + "questiontext[" + question['questiontext'].replace("\n", "\\n") + "]\n"
    if question.has_key('remotegrade'):
        log_str = log_str + "remotegrade="+str(question['remotegrade'])+"\n"
    if question.has_key('answers'):
	answers = question['answers']
	for ans in answers:
	    if ans.has_key('ansid'):
		log_str = log_str + "ansid[" + str(ans['ansid']) + "]\n"
	    if ans.has_key('answer'):
	        log_str = log_str + "answer[" + ans['answer'].replace("\n", "\\n") + "]\n"
	    if ans.has_key('tolerance'):
	        log_str = log_str + "tolerance[" + ans['tolerance'].replace("\n", "\\n") + "]\n"
    if log_str != "":
        log(log_str, 2)
#################################################################
## code to interface with R
def junk_output(s):
    return

def get_clean_R():
    for s in clean_R: r(s)
    return r

def close_R_con(R): ## procedure to clean up and close the given R connection
    for s in close_R: R(s)
    return None

def get_r_output(R, rcode):
    rcode = rcode.replace("\r\n", "\n")
    output = ""
    if rcode.strip() != '':
        output = str(R(rcode))
    return output

def load_encoded_workspace(R, workspace):
    ## tmp file name
    tmp_file = tmpdir + "/" + "rwork" + str(int(time.time())) + ".Rdata"
    fileout = open(tmp_file, "w")
    fileout.write(base64.b64decode(workspace))
    fileout.close()
    R('load("' + tmp_file + '")')
    os.remove(tmp_file)
    return R
#################################################################
def get_base64_file(filename):
    filein = open(filename, "r")
    filedata = filein.read()
    filein.close()
    return base64.b64encode(filedata)

def get_image(R, imgcode):
    ## as of R 2.7, png images work by default, so that's what we use here.
    ## it makes life much simpler
    ## first get a unique file name for R
    imgfile = tmpdir + "/" + "rimg" + str(int(time.time()))

    ## generate the image file by running the image code
    R("png(\"" + imgfile +".png\")")
    R(imgcode)
    R("dev.off()")

    ## encode the data and delete the temporary file
    dataout = get_base64_file(imgfile+".png")
    os.remove(imgfile+".png")
    return dataout

def get_R_workspace(R):
    ## tmpfile name
    workspace_tmp = tmpdir + "/" + "rwksp" + str(int(time.time())) + ".rda"
    R("save.image(file=\"" + workspace_tmp + "\")")
    dataout = get_base64_file(workspace_tmp)
    os.remove(workspace_tmp)
    return dataout
#################################################################
def process_qtext(R, qtext):
    textout = ""
    in_rcode = 0
    findstart = start = 0
    ## putting this find statement anywhere else is asking for bugs, but python
    ## doesn't seeme to want to let the nextat assignment happen in the while
    ## statement
    while (qtext.find("@", findstart) != -1):
        nextat = qtext.find("@", findstart)
        if nextat > 0 and qtext[nextat-1:nextat+1] == '\\@':
            if in_rcode == 0:
                textout = textout + qtext[start:nextat-1] + "@"
                start = nextat + 1
            findstart = nextat + 1
            continue
        if in_rcode == 0:
            ## this starts an r code chunk, so dump the preceeding bits
            textout = textout + qtext[start:nextat]
            findstart = start = nextat + 1
            in_rcode = 1
        else:
            ## process and replace r code chunk
            rcode = qtext[start:nextat].replace('\\@', '@')
            textout = textout + get_r_output(R, rcode)
            in_rcode = 0
            start = findstart = nextat + 1
    if in_rcode == 0:
        textout = textout + qtext[start:]
    else:
        rcode = qtext[start:].replace('\\@', '@')
        textout = textout + get_r_output(R, rcode)
    return textout

###########################################################################
## The functions that can be called by xmlrpc
def processquestion(question):
    global requests
    requests = requests + 1
    log("===============================process question\n")
    log_question(question)
    R = get_clean_R()
    ret = question
    ## process variables statement, don't capture output
    if question.has_key('variables'):
        ret['variables'] = get_r_output(R, question['variables'])
    ## process image code if it exists, and capture the base 64 encoded
    ## image output
    if question.has_key('imagecode') and question['imagecode'] != "":
	ret['image'] = get_image(R, question['imagecode']);
    ## process question text
    if question.has_key('questiontext'):
        ret['questiontext'] = process_qtext(R, question['questiontext'])
    ## process answers, but only if we aren't remote grading.
    ## if we are remote grading we send back a copy of the workspace so
    ## they can send it back to us when it comes time to grade
    remote_grade = 0
    if question.has_key('remotegrade'):
        remote_grade = int(question['remotegrade'])
    if remote_grade == 1:
        ret['workspace'] = get_R_workspace(R)
    elif question.has_key('answers'):
        answers_out = []
        for answer in question['answers']:
            ans = {}
            if answer.has_key('answer'):
                ans['answer'] = get_r_output(R, answer['answer'])
            if answer.has_key('tolerance'):
                ans['tolerance'] = get_r_output(R, answer['tolerance'])
            if answer.has_key('ansid'):
                ans['ansid'] = answer['ansid']
            answers_out.append(ans)
        ret['answers'] = answers_out
        ret['numanswers'] = len(answers_out)
    log("processed question\n") 
    log_question(ret) 
    close_R_con(R) 
    return ret

def status():
    R = get_clean_R()
    rv = r("version")
    close_R_con(R)
    rv['requests'] = requests
    cur_time = time.time()
    uptime = int(cur_time - start_time)
    rv['uptime'] = '%(hrs)03d:%(min)02d:%(sec)02d' % \
        {'hrs': int(uptime/3600), 'min' : int(uptime/60), 'sec': uptime % 60}
    return rv

def grade(question):
    global requests
    requests = requests + 1
    log("==================================grade question\n")
    R = get_clean_R()
    if question.has_key("workspace"):
        R = load_encoded_workspace(R, question['workspace'])
        log("received workspace\n")
        log("ls: " + get_r_output(R, "ls()") + "\n")
    ## now that we have the loaded workspace, calculate the student answer
    ## and store it in the R variable 'studentans'
	for s in grade_R: R(s)
    if question.has_key("studentans"):
        R("studentans <- \"" + str(question['studentans']) + "\"")
        log("studentans: " + get_r_output(R, "studentans") + "\n")
    ## iterate through answers, find everything that matches and return the list
    ret = []
    if question.has_key("answers"):
        for answer in question['answers']:
            if answer.has_key('answer'):
                log("checking answer: " + answer['answer'] + "\n")
                ans_result = R(str(answer['answer']))
                log("answer result: " + str(ans_result) + "\n")
                if ans_result:
                    if answer.has_key('ansid'):
                        log("answer correct, ansid: " + str(answer['ansid']) + "\n")
                        ret.append(int(answer['ansid']))
    if len(ret) == 0:
        ret.append(0)
    close_R_con(R)
    return ret

#################################################################
def read_cmdline():
	global tmpdir, logfile, loglevel, host, port, clean_R, close_R, grade_R
	config_file = ""
	opts = sys.argv[1:]
	config_idx = 0
	while config_idx < len(opts) and opts[config_idx] != "--config":
		config_idx = config_idx + 1
	if config_idx >= (len(opts)-1): 
		return None
	config_file = opts[config_idx + 1]
	cfile = open(config_file, "r")
	cfile_lines = cfile.readlines()
	cfile.close()
	####################################
	# these options are to track if such and such shows up in the config file,
	# if it is the first time for an item, we erase the array
	clean_changed  = False
	grade_changed  = False
	close_changed  = False
	tmpdir_changed = False
	clean_f = False
	grade_f = False
	close_f = False
	for l in cfile_lines:
		eq = l.find("=")
		p1 = l
		p2 = ""
		if eq != -1:
			p1 = l[:eq]
			p2 = l[(eq+1):]
		def fix_string(s):
			sharp = s.find("#")
			if sharp != -1:
				s = s[:sharp]
			return s.lstrip().rstrip()
		p1 = fix_string(p1)
		p2 = fix_string(p2)

		if p1.startswith("tmpdir"):
			if p2 != "": 
				tmpdir = p2
				tmpdir_changed = True
		elif p1.startswith("logfile"): 
			if p2 != "": logfile = p2
		elif p1.startswith("loglevel"): 
			if p2 != "": loglevel = int(p2)
		elif p1.startswith("host"): 
			if p2 != "": host = p2
		elif p1.startswith("port"): 
			if p2 != "": port = int(p2)
		elif p1.startswith("clean"): 
			if p2 != "":
				clean_changed = True
				if clean_f == False:
					clean_R = []
					clean_f = True
				clean_R.append(p2)
		elif p1.startswith("close"): 
			if p2 != "":
				close_changed = True
				if close_f == False:
					close_R = []
					close_f = True
				close_R.append(p2)
		elif p1.startswith("grade"): 
			if p2 != "":
				grade_changed = True
				if grade_f == False:
					grade_R = []
					grade_f = True
				grade_R.append(p2)
	if tmpdir_changed:
		if not clean_changed: clean_R = build_clean_R()
		if not close_changed: close_R = build_close_R()
		if not grade_changed: grade_R = build_grade_R()
#################################################################
## init R before we start the server
from rpy import r, set_rpy_output
set_rpy_output(junk_output)

if __name__ == "__main__":
	
	if len(sys.argv) > 1:
		print "Reading commandline"
		read_cmdline()
		# something should be done here to make sure the clean workspace stays okay

	# save a 'clean' R workspace that we can return to
	r("save.image(file=\""+R_clean_workspace()+"\")")

	## start the rpc server
	server = SimpleXMLRPCServer.SimpleXMLRPCServer((host, port))
	# register functions that can be called via xml-rpc
	server.register_function(processquestion)
	server.register_function(status)
	server.register_function(grade)
	server.register_introspection_functions()
	server.serve_forever()
