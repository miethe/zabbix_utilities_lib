#############################################################################
# 
# Nick Miethe 2/2019
#
# This is meant to be used as a library to be imported into any given script.
# Included are some of the more common functions used for Zabbix support scripts.
# 
#
#############################################################################

from pyzabbix import ZabbixAPI
from pyzabbix import ZabbixAPIException
import jibbix
import logging
import zabbix_secret
from twilio.rest import Client
import pyodbc
import subprocess
import urllib

#############################################################################
# Python Utilities
# Common or complex functions used frequently in scripts.
#############################################################################

class PythonUtility:

    # Executes the inputted command on the shell and returns stdout & stderr
    def call_external_cmd(self, cmd):
        # The command must be a list of strings
        proc = subprocess.Popen([str(e) for e in cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()

        return out, err

    def write_to_csv(self, filepath, data, headers):
        with open(filepath, "w", newline='') as csv_file:
            writer = csv.writer(csv_file, delimiter=',')
            writer.writerow(headers)
            for line in data:
                writer.writerow(line.split(','))
    
    def parse_csv_into_ouput(self, filepath, output, method_of_processing_into_output):
        with open(filepath, 'r') as csv_file:
            file_lines = csv.reader(csv_file, delimiter=',')
            for row in file_lines:
                method_of_processing_into_output(row, output)
        return output

    def parse_debug_argument(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-debug', action='store_true', help='Run in debug')
        args = parser.parse_args()

        if args.debug:
            return True
        return False

#############################################################################
# Twilio
# Send an sms to any number from the assigned number 
#############################################################################

class TwilioUtility:

    def send_sms(self, message, recipient):

        ASSIGNED_PHONENUMBER = ''
        # Your Account Sid and Auth Token from twilio.com/console
        ACCOUNT_SID = ''
        AUTH_TOKEN = ''

        twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)
        response = twilio_client.messages \
                .create(
                        body=message,
                        from_=ASSIGNED_PHONENUMBER,
                        to=recipient
                )
        logger = LoggerUtility().get_logger()
        logger.info('Message sent to %s: %s' % (recipient, message))
        logger.info('Response: %s' % response.sid)

#############################################################################
# Logging section
# All logging in the class is included in the log file of the calling
# class. 
# If no logger exists, one will be created as default_util.log.
#############################################################################

class LoggerUtility:
    """It is important that Logger be created before calling any other functions if logging is desired 
        or else the logs will all file into default_util.log."""
    lib_logger = None

    def __init__(self, name = 'Default Util Log', filepath = './default_util.log'):
        if self.lib_logger is None:
            self._create_logger(name, filepath)

    def _create_logger(self, name, filepath):
        log_file = filepath
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logging_handler = logging.FileHandler(log_file)
        logger_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        logging_handler.setFormatter(logger_formatter)
        logger.addHandler(logging_handler)
        
        self.lib_logger = logger

    # this should be used to create a local parameter rather than using the global logger.
    def get_logger(self):
        return self.lib_logger

#############################################################################
# PyZabbix section
#############################################################################

class PyZabbixUtility:

    def api_request(self, function, json):
        # jsonrpc and ID are auto appended by ZabbixAPI
        logger = LoggerUtility().get_logger()

        logger.info("Calling function %s" % function)
        try:
            zapi = ZabbixAPI(url=zabbix_secret.ZABBIX_URL, \
                user=zabbix_secret.AUTH_USER, password=zabbix_secret.AUTH_PASSWORD)
        except ZabbixAPIException:
            logger.warning('URL or Login is incorrect')
            raise
        except urllib2.HTTPError as err:
            if err.code == 503:
                url_try = 0
                urls = [zabbix_secret.ZABBIX_URL_BACKUP1, zabbix_secret.ZABBIX_URL_BACKUP2, zabbix_secret.ZABBIX_URL_BACKUP3]
                while url_try<=len(urls):
                    logger.warning(zabbix_secret.ZABBIX_URL + ' is not responding, trying: ' + urls[url_try])
                    try:
                        zapi = ZabbixAPI(url=urls[url_try], \
                            user=zabbix_secret.AUTH_USER, password=zabbix_secret.AUTH_PASSWORD)
                    except urllib2.HTTPError:
                        url_try+=1
                        continue
                    break


        try:
            response = zapi.do_request(function, json)['result']
            return response
        except ZabbixAPIException:
            logger.error("Trouble executing following function: " + function)
            raise

    def create_hostgroup(self, name):
        function = 'hostgroup.create'
        json = {'name':name}
        return self.api_request(function, json)

    def get_hostgroup_by_name(self, name, includeHosts=False):
        function = 'hostgroup.get'
        json = {'output':'extend', 'filter':{'name':name},'selectHosts':includeHosts}
        return self.api_request(function, json)

    # Returns groupid if found, else False
    def get_hostgroup_id_by_name(self, name, includeHosts=False):
        function = 'hostgroup.get'
        json = {'output':'groupid', 'filter':{'name':name},'selectHosts':includeHosts}
        try:
            return self.api_request(function, json)[0]['groupid']
        except:
            return False

    # Includes 'host' and 'hostid' of all hosts in Zabbix
    def get_all_host_names(self):
        function = 'host.get'
        json = {'output':['host']}
        return self.api_request(function, json)

    # Return all hostgroups
    def get_all_host_groups(self):
        function = 'hostgroup.get'
        json = {'output':'extend'}
        return self.api_request(function, json)

    # Return all hosts from a list of names
    def get_hosts_by_names(self, names):
        function = 'host.get'
        json = {'filter':{'host':[names]}}
        return self.api_request(function, json)

    def get_maintenance_by_name(self, name):
        function = "maintenance.get"
        json = {'output':'extend', 'filter':{'name':name}}
        return self.api_request(function, json)

    def get_maintenance_id_by_name(self, name):
        function = "maintenance.get"
        json = {'output':'extend', 'filter':{'name':name}}
        return self.api_request(function, json)[0]['maintenanceid']

#############################################################################
# Jira section
#############################################################################

class JiraUtility:

    class Jira_Object:
        summary = ''
        project = ''
        owner = ''
        assignee = ''
        priority = ''
        description = ''

        def __init__(self, summary, project, owner, assignee, priority, description):
            self.summary = summary
            self.project = project
            self.owner = owner
            self.assignee = assignee
            self.priority = priority
            self.description = description

    def create_jira_ticket(self, jira_object):
        logger = LoggerUtility().get_logger()
        
        info = jibbix.Info()
        info.summary  = jira_object.summary
        info.project  = jira_object.project
        info.owner = jira_object.owner
        
        info.assignee = jira_object.assignee
        info.priority = jira_object.priority
        info.description = jira_object.description
        
        jira = jibbix.open_ticket(info)

        logger.info("jibbix.open_ticket returns %s" % jira.key)

        return jira.key

    def add_jira_comment(self, key, comment):
        info = jibbix.Info()
        info.link = key
        info.description = comment
        return jibbix.comment_only(info)

#############################################################################
# For testing a purposes, an available main class
#############################################################################
if __name__ == '__main__':
    print('I compile fine, thanks.')
