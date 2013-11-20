#!/usr/bin/python
## it's important to keep this as /usr/bin/env python for cross platform
## compatibility

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import argparse
import base64
import ConfigParser
import io
import os
import SimpleXMLRPCServer
import time

################################################################################
# Define command line arguments.
parser = argparse.ArgumentParser(description='Launch an RServer process.')
parser.add_argument('--tmpdir', dest='tmpdir', type=str, nargs=1, 
    help='temporary directory.')
parser.add_argument('--logfile', dest='logfile', type=str, 
    help='logfile.', nargs=1)
parser.add_argument('--host', dest='host', type=str, nargs=1, 
    help='hostname to serve.')
parser.add_argument('--port', dest='port', type=int, nargs=1, 
    help='port to serve from.')
parser.add_argument('--loglevel', dest='loglevel', type=int, nargs=1, 
    help='logging level.  Lower means more logging.')
parser.add_argument('--config', dest='config', type=str,
    help='configuration file.', nargs=1)
parser.add_argument('--clean_r', dest='clean_r', type=str,
    help='R expressions to run to generate a clean R environment.', nargs='*')

config_values = {'tmpdir': '/tmp',
                 'logfile': 'rserver.log',
                 'host': 'localhost',
                 'port': '8080',
                 'loglevel': 1}

################################################################################

workspacetime = str(int(time.time())%1000)

def R_clean_workspace(): 
    return config_values['tmpdir'] + "/" + workspacetime + ".rda"

def build_clean_r(): 
    return ["rm(list=ls(all=TRUE))", "load(\""+R_clean_workspace()+"\")"]

def build_close_r(): 
    return ["rm(list=ls(all=TRUE))"]

def build_grade_r(): 
    return ['library(grade)']

config_values['clean_r'] = build_clean_r()
config_values['close_r'] = build_close_r()
config_values['grade_r'] = build_grade_r()
################################################################################
## this is my attempt to capture the R output, rpy made this easier
################################################################################
start_time = time.time()
requests   = 0

## logging faclities
def log(msg, level=2):
    if level > config_values['loglevel']:
        return
    with open(config_values['logfile'], "a") as logf:
        logf.write(msg)

def log_question_parameter_string(question, key):
    if not question.has_key(key):
        return ""
    return "%s[%s]\n" % (key, str(question[key]).replace("\n", "\\n"))

def log_question(question):
    log_str = "".join(log_question_parameter_string(question, key)
        for key in ['variables', 'questiontext', 'remotegrade'])
    if question.has_key('answers'):
        answers = question['answers']
        q_str = "".join(log_question_parameter_string(question, key)
            for key in ['ansid', 'answer', 'tolerance'])
        log_str = log_str + q_str 
    if log_str != "":          
       log(log_str, 2)

#################################################################
## code to interface with R
def junk_output(s):
    return

def get_clean_r():
    for s in config_values['clean_r']: r(s)
    return r

def close_r_con(R): ## procedure to clean up and close the given R connection
    for s in config_values['close_r']: R(s)
    return None

def get_r_output(R, rcode):
    rcode = rcode.replace("\r\n", "\n")
    output = ""
    if rcode.strip() != '':
        output = str(my_ri2py(R(rcode)))
    return output

def load_encoded_workspace(R, workspace):
    ## tmp file name
    tmp_file = config_values['tmpdir'] + "/" + "rwork" + str(int(time.time())) + ".Rdata"
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
    imgfile = config_values['tmpdir'] + "/" + "rimg" + str(int(time.time()))

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
    workspace_tmp = config_values['tmpdir'] + "/" + "rwksp" + \
        str(int(time.time())) + ".rda"
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
    R = get_clean_r()
    ret = question
    ## process variables statement, don't capture output
    if question.has_key('variables'):
        get_r_output(R, question['variables'])
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
    if question.has_key('remotegrade') and int(question['remotegrade']):
        ret['workspace'] = get_R_workspace(R)
    elif question.has_key('answers'):
        answers_out = []
        for answer in question['answers']:
            ans = dict((k, get_r_output(R, answer[k])) \
              for k in ['answer' , 'tolerance'] if k in answer)
            if 'ansid' in answer:
                ans['ansid'] = answer['ansid']
            answers_out.append(ans)
        ret['answers'] = answers_out
        ret['numanswers'] = len(answers_out)
    log("processed question\n") 
    log_question(ret) 
    close_r_con(R) 
    return ret

def status():
    R = get_clean_r()
    rv   = my_ri2py(R("version"))
    nmrv = my_ri2py(R("names(version)"))
    close_r_con(R)
    rv = dict(zip(nmrv, rv))
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
    R = get_clean_r()
    if question.has_key("workspace"):
        R = load_encoded_workspace(R, question['workspace'])
        log("received workspace\n")
        log("ls: " + get_r_output(R, "ls()") + "\n")
    ## now that we have the loaded workspace, calculate the student answer
    ## and store it in the R variable 'studentans'
	for s in config_values['grade_r']: R(s)
    if question.has_key("studentans"):
        R("studentans <- \"" + str(question['studentans']) + "\"")
        log("studentans: " + get_r_output(R, "studentans") + "\n")
    ## iterate through answers, find everything that matches and return the list
    ret = []
    if question.has_key("answers"):
        for answer in question['answers']:
            if answer.has_key('answer'):
                log("checking answer: " + answer['answer'] + "\n")
                ans_result = R(str(answer['answer']))[0]
                log("answer result: " + str(ans_result) + "\n")
                if ans_result:
                    if answer.has_key('ansid'):
                        log("answer matches, ansid: " + \
                            str(answer['ansid']) + "\n")
                        ret.append(int(answer['ansid']))
    if len(ret) == 0:
        ret.append(0)
    close_r_con(R)
    return ret

#################################################################
def load_configfile(filename):
    # Read and parse a config file.
    config = ConfigParser.SafeConfigParser()
    try:
        config.read(filename)
    except ConfigParser.MissingSectionHeaderError:
        # config file doesn't have a section header, so we'll make one up.
        config_bytes = "[default]\n" + open(filename).read()
        config.readfp(io.BytesIO(config_bytes))
    else:
        # The config file has other sections, we only want it to have "default".
        # Take all of the options that are not in a "default" section and
        # move them into default.
        sections = config.sections()
        if "default" not in sections:
            config.add_section("default")
        sections.remove("default")
        for section in sections:
            for key, value in config.items(section):
                config.set("default", key, value)
    config_dict = dict(config.items("default"))
    # The rest of the code expects these values to be lists.
    for key in ['grade_r', 'clean_r', 'close_r']:
        if key in config_dict:
            config_dict[key] = [config_dict[key]]
    return config_dict

def read_cmdline(args):
    # Parse config file and command line configuration options.  Options
    # more than one place are taken from, command line, config file, or the 
    # defaults, in that order.
    global config_values 
    configured_options = dict()
    parsed_args = dict((k, v) for k, v in vars(parser.parse_args(args)).items() 
        if v is not None)
    # De-list most of the args.
    for k in parsed_args:
        if k not in ['clean_r', 'grade_r', 'closer_r']:
            parsed_args[k] = parsed_args[k][0]
    if 'config' in parsed_args and parsed_args['config'] is not None:
        configured_options.update(load_configfile(parsed_args['config'][0]))
        del parsed_args['config']
    configured_options.update(parsed_args)
    config_values.update(configured_options)
    # If build_r, clean_r, grade_r or tmpdir were specicfied, we need to update 
    # those global values.
    if 'tmpdir' in configured_options:
        if 'clean_r' not in configured_options:
            config_values['clean_r'] = build_clean_r()
        if 'grade_r' not in configured_options:
            config_values['grade_r'] = build_grade_r()
        if 'close_r' not in configured_options:
            config_values['close_r'] = build_close_r()

#################################################################
def my_ri2py_inner(x):
    if not hasattr(x, '__getitem__'):
        return x
    if type(x) is str:
        return x
    elif isinstance(x, robjects.Vector):
        return my_ri2py(x)
    else:
        return x[0]

def my_ri2py(obj):
	res = robjects.default_ri2py(obj)
	if isinstance(res, robjects.Vector):
		if len(res) == 1:
			res = res[0]
		else:
			res = [my_ri2py_inner(x) for x in res]
	return res


#################################################################
## init R before we start the server
import rpy2.robjects as robjects
r = robjects.r

if __name__ == "__main__":
    read_cmdline(sys.argv[1:])

	# save a 'clean' R workspace that we can return to
    r("save.image(file=\"" + R_clean_workspace() + "\")")
    print "Saved a clean workspace in %s" % R_clean_workspace()
    print "tmpdir:", config_values['tmpdir']
    print "logfile:", config_values['logfile']

    ## start the rpc server
    address = (config_values['host'], config_values['port'])
    server = SimpleXMLRPCServer.SimpleXMLRPCServer(address)
    # register functions that can be called via xml-rpc
    server.register_function(processquestion)
    server.register_function(status)
    server.register_function(grade)
    server.register_introspection_functions()
    print "Calling serve_forever with host: %s port: %d" % address
    server.serve_forever()
