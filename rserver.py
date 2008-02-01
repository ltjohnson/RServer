#!/usr/bin/env python
## it's important to keep this as /usr/bin/env python for cross platform
## compatibility

import cgi, re

## get cgi form
form = cgi.FieldStorage()
update_str  = "Update"
process_str = "Process"
action_str  = "rserver.sh" ## crude hack to get around some environment
                           ## variable troubles, this can go away when we
			   ## get the R libs into the ld path

################################################################################
## process form
def get_form_data():
    datain = {}
    ## first get the datain
    try:
        datain['variables'] = form["variables"].value
        datain['variables'] = datain['variables'].replace("\r", "\n")
    except:
        datain['variables'] = ""
    try:
        datain['questiontext'] = form["questiontext"].value
    except:
        datain['questiontext'] = ""
    try:
        datain['numanswers'] = int(form["numanswers"].value)
        if datain['numanswers'] < 1: datain['numanswers'] = 1
    except:
        datain['numanswers'] = 1
    answers = []
    for i in range(datain['numanswers']):
        idx = "[" + str(i) + "]"
        tol_str = "tolerance" + idx
        ans_str = "answer" + idx
        ans_id_str = "ansid" + idx
        try:
            ans = form[ans_str].value
        except:
            ans = ""
        try:
            tol = form[tol_str].value
        except:
            tol = ""
        try:
            ans_id = form[ans_id_str].value
        except:
            ans_id = 0
        answers.append( (ans, tol, ans_id) )
    datain['answers'] = answers
    return datain

def get_r_output(r, rcode):
    return str(r(rcode))

def process_qtext(r, qtext):
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
            textout = textout + get_r_output(r, rcode)
            in_rcode = 0
            start = findstart = nextat + 1
    if in_rcode == 0:
        textout = textout + qtext[start:]
    else:
        rcode = qtext[start:].replace('\\@', '@')
        textout = textout + get_r_output(r, rcode)
    return textout

## junk output 
def junk_output(s):
	return

def do_r_processing():
    datain = get_form_data()
    dataout = datain
    from rpy import r, set_rpy_output
    set_rpy_output(junk_output)
    ## process variables statement, don't capture output
    if datain.has_key('variables') and datain['variables'] != '':
        dataout['variables'] = r(datain['variables'])
    ## process question text
    if datain.has_key('questiontext'):
        dataout['questiontext'] = process_qtext(r, datain['questiontext'])
    ## process answers
    if datain.has_key('answers'):
        answers_out = []
        for (a,t,ans_id) in datain['answers']:
            ans_out = get_r_output(r, a)
            tol_out = get_r_output(r, t)
            answers_out.append( (ans_out, tol_out,ans_id) )
        dataout['answers'] = answers_out
    return dataout
        
def process_form():
    print "Content-Type: text/xml\n"
    dataout = do_r_processing()
    ## now build the xml object
    from xml.dom.minidom import Document
    doc = Document()
    qml = doc.createElement("question")
    doc.appendChild(qml)
    if dataout.has_key('variables'):
        variables = doc.createElement("variables")
        variables.appendChild(doc.createTextNode(str(dataout['variables'])))
        qml.appendChild(variables)
    if dataout.has_key('questiontext'):
        qtext = doc.createElement("questiontext")
        qtext.appendChild(doc.createTextNode(str(dataout['questiontext'])))
        qml.appendChild(qtext)
    if dataout.has_key("numanswers"):
        numml = doc.createElement("numanswers")
        numml.appendChild(doc.createTextNode(str(dataout["numanswers"])))
        qml.appendChild(numml)
    if dataout.has_key("answers"):
        for (ans,tol,ansid) in dataout["answers"]:
            idml = doc.createElement("answerid")
            idml.appendChild(doc.createTextNode(str(ansid)))
            qml.appendChild(idml)
            ansml = doc.createElement("answer")
            ansml.appendChild(doc.createTextNode(str(ans)))
            qml.appendChild(ansml)
            tolml = doc.createElement("tolerance")
            tolml.appendChild(doc.createTextNode(str(tol)))
            qml.appendChild(tolml)
    print doc.toprettyxml(indent="  ")

################################################################################
## stuff to print out the html form
def get_input_form(num_answers=1):
    s = '<form action="' + action_str + '" method="post">';
    s = s + 'Variables: <textarea rows="4" cols="60" maxlength="1024" name="variables"></textarea><br>';
    s = s +'Question Text: <textarea rows="15" cols="45" name="questiontext"></textarea><br>';
    s = s + 'NumAnswers: <input name="numanswers" type="text" value="' + str(num_answers) + '"></br>';
    for i in range(num_answers):
        idx = "[" + str(i) + "]"
        s = s + 'Answer' + idx + ': <textarea rows="4" cols="60" maxlength="1024" name="answer' + idx + '"></textarea><br>';
        s = s + 'Tolerance' + idx + '<input name="tolerance' + idx + '" type="text"/></br>';
    s = s + '<input name="submit" type="submit" value="' + update_str + '"></br>';
    s = s + '<input name = "submit" type="submit" value="' + process_str + '"></br>';
    s = s + '</form>';
    return s;

def display_form():
    try:
        num_answers = int(form["numanswers"].value)
        if (num_answers < 1): num_answers = 1
    except:
        num_answers = 1
    
    print "Content-Type: text/html\n\n"
    print '<html><body>';
    print get_input_form(num_answers);
    print '</body></html>';

################################################################################
## choose action to take
try:
    action = form["submit"].value
except:
    action = None

if action == process_str:
    process_form()
else:
    display_form()
