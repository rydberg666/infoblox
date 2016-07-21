#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import os.path
import numpy
import pandas

class colors:
    YELLOW = '\033[33m'
    RED = '\033[91m'
    ENDCOLOR = '\033[0m'

def perr(module, message):
    print colors.RED + " [E] [" + module + "]" + "\t> " + message + colors.ENDCOLOR
    exit(1)

def pwarn(module, message):
    print colors.YELLOW + " [W] [" + module + "]" + "\t> " + message + colors.ENDCOLOR

def pinfo(module, message):
    print " [I] [" + module + "]" + "\t> " + message,


def help():
    perr ("System", "ERROR. Can't read file \n\nUsage " + sys.argv[0] + " <ipamfile> <bootpfile>  \nExample " + sys.argv[0] + " 101_ipam.csv 101_bootp.csv\n")
    sys.exit(1)

if len(sys.argv) != 3:
    help()
#Create temporary file containing ipam data
try:
    input_file_ipam = open(sys.argv[1], "r")
except:
    help()
#Create temporary file containing bootp data
try:
    input_file_bootp = open(sys.argv[2], "r")
except:
    help()
#Create the outputfile
try:
    output_file = open(sys.argv[1][0:3] + "_IB.csv", "w")
except:
    help()



#Create temporary file for bootp data and add column names since they are absent
tempfile = open(sys.argv[1][0:3] + "_IB.tmp", "w")
tempfile.write("fqdn macaddress IPAddress Reply\n")

#Create temporary file for ipam data
tempfile2 = open(sys.argv[1][0:3] + "_ipam.tmp", "w")


#Eliminate UpperCaseHUManErrOrs, replace characters to conform with IB, set Column headers
for line in input_file_ipam:
    line = line.lower()
    line = line.replace("device name", "fqdn")
    line = line.replace("asset tag", "EA-Inventarie")
    line = line.replace("description", "EA-Modell")
    line = line.replace("cost", "EA-Kostnadsstalle")
    line = line.replace("hardware", "EA-Hardvarutyp")
    line = line.replace("others", "EA-Beskrivning")
    line = line.replace("room", "EA-Rum")
    line = line.replace("�", "oe")
    line = line.replace("å", "a")
    line = line.replace("ä", "ae")
    line = line.replace("ö", "oe")
    tempfile2.write(line)
tempfile2.close
tempfile2 = open(sys.argv[1][0:3] + "_ipam.tmp", "r")

#Search and replace unwanted text from bootp data
for line in input_file_bootp:
    line = line.lower()
    if "true" in line:
        line = line.replace(" true", "")
        line = line[:-2] + "true\n"
    else:
        line = line[:-2] + "false\n"
    line = line.replace("{", "")
    line = line.replace("}", "")
    line = line.replace(";", "")
    line = line.replace("hardware ethernet", "")
    line = line.replace("host ", "")
    line = line.replace("fixed-address", "")
    line = line.replace("always-reply-rfc1048", "")
    line = line.replace("   ", " ")
    line = line.replace("  ", " ")
    if not line.startswith("#"):
        tempfile.write(line)
tempfile.close()
tempfile = open(sys.argv[1][0:3] + "_IB.tmp", "r")


#Create datafield from the cleaned up ipam data only containing the columns we want
df = pandas.read_csv(tempfile2)
keep_cols = ["fqdn", "ip address", "EA-Inventarie", "EA-Modell", "EA-Kostnadsstalle", "EA-Hardvarutyp", "EA-Beskrivning", "EA-Rum"]
new_df_ipam = df[keep_cols]


new_df_ipam['EA-Inventarie'] = pandas.to_numeric(new_df_ipam['EA-Inventarie'], errors='coerce')



new_df_ipam['EA-Inventarie'] = new_df_ipam['EA-Inventarie'].fillna(699699)
new_df_ipam['EA-Inventarie'] = new_df_ipam['EA-Inventarie'].astype(int)
new_df_ipam.loc[new_df_ipam['EA-Inventarie']>699698, 'EA-Inventarie'] = ' '




#print new_df_ipam.dtypes

 
#Create datafield from the cleaned up bootp data containing the columns we need, set delimiter to ' '
df2 = pandas.read_csv(tempfile, delimiter=' ')
keep_cols2 = ["fqdn","macaddress", "Reply"]
new_df_bootp = df2[keep_cols2]


#create the final datafield by merging data, removing NaN with ' ', add True for dhcp when there is a MAC
#Add domainsuffix to create fqdn for Hosts. Final Format for IB compliance
test = pandas.merge(new_df_ipam, new_df_bootp, on='fqdn', how='left')
test = test.fillna(' ')
test = test.rename(columns={'ip address': 'Addresses'})
test = test.rename(columns={'macaddress': 'Mac_address'})
test = test.rename(columns={'Reply': 'EA-Replyrfc'})
test['configure_for_dhcp'] = numpy.where(test['Mac_address'] == ' ', 'False', 'True')
test['configure_for_dns'] = 'True'
test['fqdn'] = test['fqdn'].astype(str) + '.sts.sll.se'
test['Header-HostRecord'] = 'HostRecord' 
test = test[['Header-HostRecord','fqdn', 'configure_for_dns', 'configure_for_dhcp', 'Mac_address', 'Addresses', 'EA-Inventarie', 'EA-Modell', 'EA-Kostnadsstalle', 'EA-Hardvarutyp', 'EA-Beskrivning', 'EA-Rum', 'EA-Replyrfc']]

test.to_csv(output_file, index=False)
os.remove(sys.argv[1][0:3] + "_IB.tmp")
os.remove(sys.argv[1][0:3] + "_ipam.tmp")

