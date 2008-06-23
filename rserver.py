#!/usr/bin/python
## it's important to keep this as /usr/bin/env python for cross platform
## compatibility

################################################################################
# all of these options are defaults and configurable in the config file
tmpdir   = "/home/ruser/rserver_tmp"
logfile  = "/home/ruser/log/rserver.log"
loglevel = 1

R_clean_workspace = tmp_dir + "/" + "work" + str(int(time.time())%1000) + ".rda"

host = "rweb.stat.umn.edu"
port = 3030

clean_R = ["rm(list=ls(all=TRUE))", "load(\""+R_clean_workspace+"\")"]
close_R = ["rm(list=ls(all=TRUE))"]
grade_R = ['library(grade, lib.loc="/home/ruser/R-library")']
################################################################################


import SimpleXMLRPCServer
import base64, time, os
#############################################
## this probably should be configurable in some way

#################################################################
## logging faclities
def log(msg, level=1)]
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
    for s in clean_r: r(s)
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
    tmp_file = tmp_dir + "/" + "rwork" + str(int(time.time())) + ".Rdata"
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
    ## first get a unique file name for R
    imgfile = tmp_dir + "/" + "rimg" + str(int(time.time()))
    #R("png(\"" + imgfile +"\")")
    # png images don't work without x running, it might be worth the trouble
    # to get it attached to an x session if available
    R("postscript(\""+imgfile+".ps\")")
    R(imgcode)
    R("dev.off()")
    ## now that we have the image file, we will binary encode it and return it
    os.system("convert "+imgfile+".ps -rotate 90 -resize 640x480 "+ imgfile +".png")
    dataout = get_base64_file(imgfile+".png")
    ## remove the file and return the encoded data
    os.remove(imgfile+".png")
    os.remove(imgfile+".ps")
    return dataout

def get_R_workspace(R):
    ## tmpfile name
    workspace_tmp = tmp_dir + "/" + "rwksp" + str(int(time.time())) + ".rda"
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
    close_R(R) 
    return ret

def status():
    R = get_clean_R()
    rv = r("version")
    close_R(R)
    return rv

def grade(question):
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
    close_R(R)
    return ret

#################################################################
## init R before we start the server
from rpy import r, set_rpy_output
set_rpy_output(junk_output)
# save a 'clean' R workspace that we can return to
r("save.image(file=\""+R_clean_workspace+"\")")

## start the rpc server
server = SimpleXMLRPCServer.SimpleXMLRPCServer((host, port))
# register functions that can be called via xml-rpc
server.register_function(processquestion)
server.register_function(status)
server.register_function(grade)
server.register_introspection_functions()
server.serve_forever()
