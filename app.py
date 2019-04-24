
# coding: utf-8

# In[ ]:
import os
from github import Github
g = Github(os.environ['GITKEY'])
from flask import Flask, request, render_template
app = Flask(__name__)

import requests
import random
#Utilities for expressing natural time
import datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
def getURL(url,quiet=False):
    if not quiet: print(url)
    r=requests.get(url)
    if not quiet: print(r.status_code)
    return r

def loader(url,quiet=True):
    items=[]
    done=False
    r=getURL(url)
    while not done:
        items=items+r.json()['result']['items']
        if 'next' in r.json()['result']:
            r=getURL(r.json()['result']['next']+'&_pageSize=500')
        else: done=True
    return items



#This is a bit of utility code that helps us count how work is allocated
#https://github.com/timdiels/chicken_turtle_util/blob/master/chicken_turtle_util/algorithms.py
class _handler(object):
    def __init__(self,_name):
        self._name = _name
        self._items = []
        self._itemCounts = []
        self._count_sum = 0
        
    def add(self, item, count):
        self._items.append(item)
        self._itemCounts.append((item,count))
        self._count_sum += count
    
    @property
    def name(self):
        return self._name
    
    @property
    def items(self):
        return (self._items, self._count_sum)
    
    @property
    def itemCounts(self):
        return (self._itemCounts, self._count_sum)
    
    @property
    def count_sum(self):
        return self._count_sum

@app.route("/")
def hello(): 
    return render_template('index.html')

@app.route('/resultpage', methods=['POST'])
def my_form_post():
    text = request.form['Date']
    handling = request.values.getlist('hello')
    url='http://lda.data.parliament.uk/commonswrittenquestions.json?min-dateTabled={}&_pageSize=500'.format(text)
   #The API returns a list of written questions on/since the specified date
    items=loader(url)
    def getAnsweringBody(item):
        rel=[]
        for body in item['AnsweringBody']:
            rel.append(body['_value'])
        return rel
    rels=[rel for s in [getAnsweringBody(q) for q in items] for rel in s]

    #Also flag where there were multiple bodies?
    #multibody=[m for m in [getAnsweringBody(q)  for q in items] if len(m)>1]
    #if multibody: print("Some requests appear to be targeted at multiple bodies:", m)

    #Display the answering body for the first few questions
    df=pd.DataFrame(rels)
    df.columns=['Answering Body']
    df
    dfc=df.groupby('Answering Body').size().rename('Count').reset_index().sort_values('Count',ascending=False)
    #dfc.head()
    random.shuffle(handling)
    handlers=handling
    print(handlers)
    #Are there any requirements as to whom particular targeted answering bodies will specifically be allocated to?
    handlerPrefs={}
    #We should perhaps also check that there are no collisions in prefs
    #For example, if two or more people have the same pref, randomly pick who will get it?


    #Are there any requirements as to which particular targeted answering bodies must not be allocated to a particular person?
    handlerAvoid={}
    handlerJobs=[_handler(h) for h in handlers]
    handled=[]

    #First of all, allocate according the preferences (actually, we treat these as *required* allocations)
    for handler_ in handlerJobs: 
        if handler_.name in handlerPrefs:
            for ix,row in dfc[dfc['Answering Body'].isin(handlerPrefs[handler_.name])].iterrows():
                #Add a start to an answering body name of the allocation was required
                handler_.add(row['Answering Body']+'*',row['Count'])
                handled.append(row['Answering Body'])

    #Allocating the work is an example of a multi-way partition problem.
    #This sort of problem can be quite hard to solve exactly, but there are heuristics
    #Eg allocate from largest job to lowest; give next job to person with least load overall
    for ix,row in dfc[~dfc['Answering Body'].isin(handled)].iterrows():
        #Note the 'if not' tweak to the allocation so someone who wants to avoid an answering body actually does so...
        handler_ = min(handlerJobs, key=lambda handler_: handler_._count_sum if not (handler_.name in handlerAvoid and row['Answering Body'] in handlerAvoid[handler_.name])  else float('inf')  ) 
        handler_.add(row['Answering Body'],row['Count'])
    
        
    #Or more prettily...
    #for h in handlerJobs:
        #abtxt=''.join([' {} for the {}'.format(b[1], b[0]) for b in h.itemCounts[0]])
        #questionsoutput = '{} needs to tag {} questions:{}'.format(h.name, h.itemCounts[1],abtxt)
        #print(questionsoutput)
        
    questions = handlerJobs    
    dfq = pd.DataFrame([vars(q) for q in questions])
    print(dfq)
    from datetime import datetime
    timenow= str(datetime.now())
    user = g.get_user()
    repo = user.get_repo("wpqhandler")
    print(repo)
    file = repo.get_file_contents("/license.csv")
    print(file)
    repo.update_file("/license.csv", timenow, dfq, file.sha)
         
    return render_template('resultpage.html', questions = questions, handling = handling)
if __name__ == "__main__":
  app.debug = True
  app.run(port=5005, use_reloader=False)

