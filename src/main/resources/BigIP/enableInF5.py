# THIS CODE AND INFORMATION ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS
# FOR A PARTICULAR PURPOSE. THIS CODE AND INFORMATION ARE NOT SUPPORTED BY XEBIALABS. 
#

import sys
import java.lang.System as System
import java.text.SimpleDateFormat as Sdf
import java.sql.Date as Date


from java.lang import Exception
from java.io import PrintWriter
from java.io import StringWriter
from java.lang import ClassLoader

from com.xebialabs.overthere import CmdLine, ConnectionOptions, OperatingSystemFamily, Overthere
from com.xebialabs.overthere.ssh import SshConnectionBuilder
from com.xebialabs.overthere.ssh import SshConnectionType
from com.xebialabs.overthere.util import CapturingOverthereExecutionOutputHandler, OverthereUtils

class SshRemoteScript():
    def __init__(self, username, password, address, connectionType, script):
        self.options = ConnectionOptions()
        self.options.set(ConnectionOptions.USERNAME, username)
        self.options.set(ConnectionOptions.PASSWORD, password)
        self.options.set(ConnectionOptions.ADDRESS, address)
        self.options.set(ConnectionOptions.OPERATING_SYSTEM, OperatingSystemFamily.WINDOWS)

        self.script = script
        self.connectionType = connectionType

        self.stdout = CapturingOverthereExecutionOutputHandler.capturingHandler()
        self.stderr = CapturingOverthereExecutionOutputHandler.capturingHandler()

    def customize(self, options):
        if self.connectionType == 'SFTP':
            options.set(SshConnectionBuilder.CONNECTION_TYPE, SshConnectionType.SFTP)
        elif self.connectionType == 'SCP':
            options.set(SshConnectionBuilder.CONNECTION_TYPE, SshConnectionType.SCP)
        elif self.connectionType == 'SSH':
            options.set(SshConnectionBuilder.CONNECTION_TYPE, SshConnectionType.SSH)
        #print 'DEBUG: Options:', options

    def execute(self):
        self.customize(self.options)
        connection = None
        try:
            connection = Overthere.getConnection(SshConnectionBuilder.CONNECTION_TYPE, self.options)
            # upload the script and pass it to cscript.exe
            exeFile = connection.getTempFile('f5_disable', '.py')
            OverthereUtils.write(String(self.script).getBytes(), targetFile)
            exeFile.setExecutable(True)
            # run cscript in batch mode
            scriptCommand = CmdLine.build( '/usr/bin/python', exeFile.getPath() )
            return connection.execute(self.stdout, self.stderr, scriptCommand)
        except Exception, e:
            stacktrace = StringWriter()
            writer = PrintWriter(stacktrace, True)
            e.printStackTrace(writer)
            self.stderr.handleLine(stacktrace.toString())
            return 1
        finally:
            if connection is not None:
                connection.close()

    def getStdout(self):
        return self.stdout.getOutput()

    def getStdoutLines(self):
        return self.stdout.getOutputLines()

    def getStderr(self):
        return self.stderr.getOutput()

    def getStderrLines(self):
        return self.stderr.getOutputLines()

scriptFile = """
#!/usr/bin/python

import pycontrol.pycontrol as pc
import getpass
import sys
from sys import argv

bigip_address = '%s'
bigip_user = '%s'
bigip_pass = '%s
active_partition = '%s'
poolmember_pool = '%s'
poolmember_address = '%s'
poolmember_port = '%s'

print 'Connecting to BIG-IP at [' + bigip_address + '] as user [' + bigip_user + ']'
bigip = pc.BIGIP(hostname = bigip_address, username = bigip_user, password = bigip_pass, fromurl = True, wsdls = ['Management.Partition', 'LocalLB.Pool', 'LocalLB.PoolMember'])

pool = bigip.LocalLB.Pool
pool_version = pool.get_version()
print 'Detected version: ' + pool_version

print 'Setting active partition to [' + active_partition + ']'
bigip.Management.Partition.set_active_partition(active_partition)

try:
    setter = pool.set_member_monitor_state
    legacy_api = 0
except AttributeError:
    legacy_api = 1

if legacy_api:
    pmem = bigip.LocalLB.PoolMember.typefactory.create('Common.IPPortDefinition')
    pmem.address = poolmember_address
    pmem.port = poolmember_port

    # session state
    sstate = bigip.LocalLB.PoolMember.typefactory.create('LocalLB.PoolMember.MemberSessionState')
    sstate.member = pmem
    sstate.session_state = 'STATE_DISABLED'

    sstate_seq = bigip.LocalLB.PoolMember.typefactory.create('LocalLB.PoolMember.MemberSessionStateSequence')
    sstate_seq.item = [sstate]

    print 'Disabling pool member [' + poolmember_address + ':' + poolmember_port + '] in pool [' + poolmember_pool + ']'
    bigip.LocalLB.PoolMember.set_session_enabled_state(pool_names = [poolmember_pool], session_states = [sstate_seq])

    # monitor state
    mstate = bigip.LocalLB.PoolMember.typefactory.create('LocalLB.PoolMember.MemberMonitorState')
    mstate.member = pmem
    mstate.monitor_state = 'STATE_DISABLED'

    mstate_seq = bigip.LocalLB.PoolMember.typefactory.create('LocalLB.PoolMember.MemberMonitorStateSequence')
    mstate_seq.item = [mstate]

    print 'Forcing pool member [' + poolmember_address + ':' + poolmember_port + '] in pool [' + poolmember_pool + '] offline'
    bigip.LocalLB.PoolMember.set_monitor_state(pool_names = [poolmember_pool], monitor_states = [mstate_seq])
else:
    pmem = pool.typefactory.create('Common.AddressPort')
    pmem.address = poolmember_address
    pmem.port = int(poolmember_port)

    pmem_seq = pool.typefactory.create('Common.AddressPortSequence')
    pmem_seq.item = [pmem]

    state = pool.typefactory.create('Common.EnabledState').STATE_DISABLED
    state_seq = pool.typefactory.create('Common.EnabledStateSequence')
    state_seq.item = [state]

    # session state
    print 'Disabling pool member [' + poolmember_address + ':' + poolmember_port + '] in pool [' + poolmember_pool + ']'
    pool.set_member_session_enabled_state(pool_names = [poolmember_pool], members= [pmem_seq], session_states = [state_seq])

    # monitor state
    print 'Forcing pool member [' + poolmember_address + ':' + poolmember_port + '] in pool [' + poolmember_pool + '] offline'
    pool.set_member_monitor_state(pool_names = [poolmember_pool], members= [pmem_seq], monitor_states = [state_seq])

print 'Done'
""" % ( bigIpAddress, bigIpUser, bigIpPass, activePartition, poolMemberPool, poolMemberAddress, poolMemberPort )



script = SshRemoteScript(username, password, address, connectionType, scriptFile)
exitCode = script.execute()

output = script.getStdout()
err = script.getStderr()

if (exitCode == 0):
    print scriptFile
    print "----"
    print output
else:
    print "Exit code "
    print exitCode
    print
    print "#### Output:"
    print output

    print "#### Error stream:"
    print err
    print
    print "----"

    #sys.exit(exitCode)
    sys.exit(0)

