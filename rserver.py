#!/usr/bin/env python
## it's important to keep this as /usr/bin/env python for cross platform
## compatibility


import SimpleXMLRPCServer
import base64, time, os
#############################################
## this probably should be configurable in some way
host = "localhost"
port = 8080

tmp_dir = "/home/leif/rserver_tmp"

#################################################################
## logging faclities
def log(msg):
    logfile = open("/home/leif/log/rserver.log", "a")
    logfile.write(msg)
    logfile.close()
    return None
def log_question(question):
    log_str = ""
    if question.has_key('variables'):
	    log_str = log_str + "variables[" + question['variables'].replace("\n", "\\n") + "]\n"
    if question.has_key('questiontext'):
	log_str = log_str + "questiontext[" + question['questiontext'].replace("\n", "\\n") + "]\n"
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
        log(log_str)
#################################################################
## code to interface with R
def junk_output(s):
    return
    
def get_clean_R():
    from rpy import r, set_rpy_output
    set_rpy_output(junk_output)
    return r

def close_R(R): ## procedure to clean up and close the given R connection
    R("rm(list=ls(all=TRUE))")
    return None

def get_r_output(R, rcode):
    rcode = rcode.replace("\r\n", "\n")
    output = ""
    if rcode.strip() != '':
        output = str(R(rcode))
    return output
#################################################################
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
    filein = open(imgfile+".png", "r")
    filedata = filein.read()
    filein.close()
    dataout = base64.b64encode(filedata)
    ## remove the file and return the encoded data
    os.remove(imgfile+".png")
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

    
def processquestion(question):
    log("received question\n")
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
    ## process answers
    if question.has_key('answers'):
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
        
#################################################################
## star the rpc server
server = SimpleXMLRPCServer.SimpleXMLRPCServer((host, port))
server.register_function(processquestion)
server.register_introspection_functions()
server.serve_forever()
