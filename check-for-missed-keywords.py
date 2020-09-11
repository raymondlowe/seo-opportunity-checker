#!/usr/bin/env python3

# Uses code from https://github.com/raymondlowe/Google-analytics-and-search-console
#

import argparse
import requests
import requests_cache
import pandas as pd
import datetime
from progress.bar import IncrementalBar
from googleAPIget_service import get_service
from urllib.parse import urlparse

testonly = True

def parse(haystack, needle):
    print("Checking for ["+needle+"] in "+haystack)
    try:
        page = requests.get(haystack)
    except:
        print("Fail")
        return -1
    lowerpagetext = page.text.lower()
    lowerneedle = needle.lower()
    result = lowerpagetext.count(lowerneedle)
    print (result)
    return result
  


requests_cache.install_cache('page_cache')


parser = argparse.ArgumentParser()


parser.add_argument(
    "period_days", help="Number of days back to check data", default=7, type=int)
parser.add_argument("-n", "--name", default='check-for-missed-keywords-report.xlsx', type=str,
                    help="File name for final output, default is check-for-missed-keywords-report + the current date. You do NOT need to add file extension")
parser.add_argument("-g", "--googleaccount", type=str, default="", help="Name of a google account; does not have to literally be the account name but becomes a token to access that particular set of secrets. Client secrets will have to be in this a file that is this string concatenated with client_secret.json.  OR if this is the name of a text file then every line in the text file is processed as one user and all results appended together into a file")

args = parser.parse_args()

period_days = args.period_days

dimensionsstring = "page,query"
dimensionsarray = dimensionsstring.split(",")
multidimention = len(dimensionsarray) > 1

dataType = "web"

name = args.name

googleaccountstring = args.googleaccount

if name == 'check-for-missed-keywords-report.xlsx':
    name = 'check-for-missed-keywords-report-' + \
        datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

scope = ['https://www.googleapis.com/auth/webmasters.readonly']

try:
    googleaccountslist = open(googleaccountstring).read().splitlines()
    # remove empty lines
    googleaccountslist = [x.strip() for x in googleaccountslist if x.strip()]
except:
    googleaccountslist = [googleaccountstring]


combinedDF = pd.DataFrame()

if testonly:
    breakcounter = 0

for thisgoogleaccount in googleaccountslist:
    breakcounter =+ 1
    if breakcounter > 2:
        break
    print("Processing: " + thisgoogleaccount)
    # Authenticate and construct service.
    service = get_service('webmasters', 'v3', scope, 'client_secrets.json', thisgoogleaccount)
    profiles = service.sites().list().execute()
    #profiles is now list    

    #print("Len Profiles siteEntry: " + str(len(profiles['siteEntry'])))

    bar = IncrementalBar('Processing',max=len(profiles['siteEntry']))


    bigdf = pd.DataFrame()
    if testonly:
        breakcounter2 = 0

    for item in profiles['siteEntry']:
        breakcounter2 =+ 1
        if breakcounter2 > 4:
            break
        bar.next()
        if item['permissionLevel'] != 'siteUnverifiedUser':

            smalldf = pd.DataFrame()

            #print(item['id'] + ',' + start_date + ',' + end_date)
            results = service.searchanalytics().query(
            siteUrl=item['siteUrl'], body={
                'startDate': '2020-09-01',
                'endDate': '2020-09-07',
                'dimensions': dimensionsarray,
                'searchType': dataType,
                'rowLimit': 5000
            }).execute()

            if len(results) == 2:
                #print(results['rows'])
                #print(smalldf)
                smalldf = smalldf.append(results['rows'])
                #print(smalldf)

                if multidimention:
                    #solves key1 reserved word problem
                    smalldf[['key-1','key-2']] = pd.DataFrame(smalldf['keys'].tolist(), index= smalldf.index)
                    smalldf['keys']

                rootDomain = urlparse(item['siteUrl']).hostname
                if 'www.' in rootDomain:
                    rootDomain = rootDomain.replace('www.','')

                smalldf.insert(0,'siteUrl',item['siteUrl'])
                smalldf.insert(0,'rootDomain',rootDomain)
                #print(smalldf)
                if len(bigdf.columns) == 0:
                    bigdf = smalldf.copy()
                else:
                    bigdf = pd.concat([bigdf,smalldf])

                #print(bigdf)
    bar.finish()

    bigdf.reset_index()
    #bigdf.to_json("output.json",orient="records")

    if len(bigdf) > 0:
        bigdf['keys'] = bigdf["keys"].str[0]

        # Got the bigdf now of all the data from this account, so add it into the combined
        combinedDF = pd.concat([combinedDF,bigdf],sort=True)

    # clean up objects used in this pass
    del bigdf
    del profiles
    del service


if len(combinedDF) > 0:
    if googleaccountstring > "" :
        name = googleaccountstring + "-" + name 

    combinedDF['KeywordFound'] = -1
    combinedDF.reset_index()
    
    if testonly:
        breakcounter3 = 0
    for i in range(len(combinedDF)):      
        combinedDF['KeywordFound'].values[i] = parse(combinedDF['key-1'].values[i], combinedDF['key-2'].values[i])
        breakcounter3 =+ 1
        if breakcounter3 > 20:
            break
        
    with pd.ExcelWriter(name + '.xlsx') as writer:
        combinedDF.to_excel(writer, sheet_name='data')

        print("finished and outputed to excel file")
else:
    print("nothing found")




print("--done--")
