#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Tue Aug 2 2016 Johan Hedström <johan.hedstrom@sodertaljesjukhus.se>
# Updated xxx
#
# Mon Aug 1 2016 Johan Hedström <johan.hedstrom@sodertaljesjukhus.se>
# Cleaned up version
# Program to clean up/merge IPAM/BOOTP data from unix/MS to Infoblox 
# This program reads data from 2 files, bootp data and ipam data
# These files are cleaned up and merged into a single csv file conforming to Infoblox syntax for data import

import sys
import os
import subprocess
import os.path
import numpy
import pandas
import itertools
import re

# Colors for formatting messages to user
class colors:
    YELLOW = '\033[33m'
    RED = '\033[91m'
    ENDCOLOR = '\033[0m'
    
# Help function, informs wether if file is missing or parameterlist is wrong
def help(msg):
    print colors.RED + msg + colors.ENDCOLOR
    exit(1)
    
if len(sys.argv) != 3:
    help("Faulty parameterlist\n\nUsage " + sys.argv[0] + " ipam_data_file bootp_file")

# Open file containing ipam data for reading
try:
    input_file_ipam = open(sys.argv[1], "r")
except:
    help("Error: Could not open ipam file: " + sys.argv[1])

# Open file containing bootp data for reading
try:
    input_file_bootp = open(sys.argv[2], "r")
except:
    help("Error: Could not open bootp file: " + sys.argv[2])

# Open the final outputfile for writing and names it after input ipamfile's first 3 chars. ie "105_IB.csv"
try:
    output_file = open(sys.argv[1][0:3] + "_IB.csv", "w")
except:
    exit(1)
    
# Create temporary file for bootp data and add column names since they are absent in the unix bootp file
tempfile = open(sys.argv[1][0:3] + "_bootp.tmp", "w")
tempfile.write("fqdn macaddress IPAddress Reply\n")

# Create temporary file for ipam data
tempfile2 = open(sys.argv[1][0:3] + "_ipam.tmp", "w")

# Function that takes input and outputfiles plus dictionary as arguments, searches and replaces as needed
def replace_all(f1,f2,dic):
    for line in f1:
        # Since people have been sloppy we need to convert all text to lowercase...
        line = line.lower()

        """Bootpdata rows contain the value true for option always-reply-rfc1048, we need this moved to the
        last column to be. If the row does not contain the value true we add false instead for consistency
        """
        if "true" in line:
            line = line.replace(" true ", "")
            line = line[:-2] + " true\n"
        else:
            line = line[:-2] + " false\n"

        # Iterates our dictionary and replaces as needed for our wanted syntax
        for i,j in dic.iteritems():
            line = line.replace(i,j)
        # Replaces all pesky double, triple spaces with a single ' '
        line = re.sub('\s{2,}', ' ', line)

        """ Again, since people have been sloppy, there are left rows beginning with # in the bootfile.
        If we do not remove these we will in worst case be left with duplicate host entrys in the final
        product. Best case leaves us with a not used macaddress
        """
        if not line.startswith("#"):
            f2.write(line)
            
# Dictionary for replacement of ipam data we need corrected            
dictionary_ipam = {'å':'a', 'ä': 'ae', 'ö':'oe', 'Å': 'a',
 'Ä': 'ae', 'Ö': 'oe', 'device name' :'fqdn', 'asset tag': 'EA-Inventarie',
 'description': 'EA-Modell', 'cost': 'EA-Kostnadsstalle',
 'hardware': 'EA-Hardvarutyp',
 'others': 'EA-Beskrivning', 'room': 'EA-Rum', '�': 'oe' }   
# Dictionary for replacement of bootp data we need corrected
dictionary_bootp = {';':'', '{':'', '}': '', 'hardware ethernet ': '',
 'host': '', 'fixed-address': '', 'always-reply-rfc1048':''}

# Call function for bootp data
replace_all(input_file_bootp, tempfile, dictionary_bootp)

# Now that all changes are written to our tempfiles we close them and open them for reading again
tempfile.close()
tempfile = open(sys.argv[1][0:3] + "_bootp.tmp", "r")

# Call function for ipam data
replace_all(input_file_ipam, tempfile2, dictionary_ipam)
tempfile2.close
tempfile2 = open(sys.argv[1][0:3] + "_ipam.tmp", "r")

# Create pandas datafield from the cleaned up ipam data only containing the columns we want
df = pandas.read_csv(tempfile2)
keep_cols = ["fqdn", "ip address", "EA-Inventarie", "EA-Modell", "EA-Kostnadsstalle", "EA-Hardvarutyp", "EA-Beskrivning", "EA-Rum"]
new_df_ipam = df[keep_cols]

""" Apparently someone entered a textstring where there should only be integers, this code cleans it up
    and fills nullvalues first with a number, then sets it to ' '
"""    
new_df_ipam['EA-Inventarie'] = pandas.to_numeric(new_df_ipam['EA-Inventarie'], errors='coerce')
new_df_ipam['EA-Inventarie'] = new_df_ipam['EA-Inventarie'].fillna(699699)
new_df_ipam['EA-Inventarie'] = new_df_ipam['EA-Inventarie'].astype(int)
new_df_ipam.loc[new_df_ipam['EA-Inventarie']>699698, 'EA-Inventarie'] = ' '
 
#Create datafield from the cleaned up bootp data containing the columns we need, set delimiter to ' '
df2 = pandas.read_csv(tempfile, delimiter=' ')
keep_cols2 = ["fqdn","macaddress", "Reply"]
new_df_bootp = df2[keep_cols2]

"""create the final datafield by merging data, removing NaN with ' ', add True for dhcp when there is a MAC
   Add domainsuffix to create fqdn for Hosts. Final Format for Infoblox compliance
"""
final_df = pandas.merge(new_df_ipam, new_df_bootp, on='fqdn', how='left')
final_df = final_df.fillna(' ')
final_df = final_df.rename(columns={'ip address': 'Addresses'})
final_df = final_df.rename(columns={'macaddress': 'Mac_address'})
final_df = final_df.rename(columns={'Reply': 'EA-Replyrfc'})

# Set Infoblox flag for configure for dhcp to true where a Mac Address exists
final_df['configure_for_dhcp'] = numpy.where(final_df['Mac_address'] == ' ', 'False', 'True')
final_df['configure_for_dns'] = 'True'

# Add domain suffix as Infoblox requires fqdn for hosts
final_df['fqdn'] = final_df['fqdn'].astype(str) + '.zone_sts.local'
# ^^^^^ final_df['fqdn'] = final_df['fqdn'].astype(str) + 'CHANGE_TO_REAL_FQDN_DOMAIN' ^^^^^

# Fill all the rows with 'HostRecord' as required by Infoblox syntax
final_df['Header-HostRecord'] = 'HostRecord' 
final_df = final_df[['Header-HostRecord','fqdn', 'configure_for_dns', 'configure_for_dhcp', 'Mac_address', 'Addresses', 'EA-Inventarie', 'EA-Modell', 'EA-Kostnadsstalle', 'EA-Hardvarutyp', 'EA-Beskrivning', 'EA-Rum', 'EA-Replyrfc']]

# Export our beautiful datafield to a csvfile
final_df.to_csv(output_file, index=False)

# Clean up
tempfile.close()
tempfile2.close()
os.remove(sys.argv[1][0:3] + "_bootp.tmp")
os.remove(sys.argv[1][0:3] + "_ipam.tmp")
