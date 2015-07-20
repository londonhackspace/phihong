#!/usr/bin/env python

import serial,os,sys,argparse,textwrap,struct
from hexdump import hexdump, tobin

class Port:
  def __init__(self, name, state):
    self.name = name
    self.state = state

class Phihong:
  def __init__(self, dev="/dev/ttyUSB0"):
    self.dev = dev
    # the windows version wants you to use
    # xon and xoff flow control, really?
    self.s = serial.Serial(dev, 19200)
    self.name = ' ' * 10
    self.ports = []

    # n.b. ports not zero indexed.
    for i in range(0,25):
      self.ports.append(Port('', 1))

    # id 2.0 revision 3.3 in here somewhere.

    self.send(struct.pack('B', 0))
    ret = self.s.read(7)
    self.unpacket(ret)

    self.send(struct.pack('B', 4))
    ret = self.s.read(27)
    self.unpacket(ret)

    if self.name != ' ' * 10:
      print "System name:", self.name
  
  def cksum(self, packet):
    cksum = 0
    for i in struct.unpack('B' * len(packet), packet):
      cksum += i
    return cksum    
      
  def send(self, packet):
    cksum = self.cksum(packet)
    packet = packet + struct.pack('>H', cksum)
#    hexdump(packet)
    self.s.write(packet)
  
  def recv(self, len):
    # len is the data, not including the checksum
    packet = self.s.read(len + 2)
    cksum = self.cksum(packet[:-2])
    if cksum != struct.unpack('>H', packet[-2:])[0]:
      print hex(cksum), hex(struct.unpack('>H', packet[-2:])[0])
      print "cksum missmatch?!?"
      hexdump(packet)
      print hex(cksum)
      return None
    return packet[:-2]

  def status(self):
    # starts with 05 00
    # then goes up via 05 01 etc.
    for i in range(0, 24):
      self.send(struct.pack('BB', 5, i))
      ret = self.s.read(27)
      self.unpacket(ret)

  def otherstatus(self):
    # starts with 05 00
    # then goes up via 05 01 etc.
    for i in range(0, 24):
      self.send(struct.pack('BB', 8, i))
      ret = self.s.read(16)
      self.unpacket(ret)

  def enable(self, port):
    print "enabling", port
    # 03 03 3F E1 59 10 07
    #
    # name: ' ' * 10
    # 20 20 20 20 20 20 20 20 20 20
    #
    packet = [int(x, 16) for x in "03 03 3F E1 59 10 07".split()]
    packet[1] = port - 1
    packet = struct.pack('B' * len(packet), *packet)
    name = self.ports[port].name
    if len(name) < 10:
      name = name + ' ' * (10 - len(name))
    packet += name
    hexdump(packet)
    self.send(packet)
    ret = self.recv(2)
    if ret != "\x03\x00":
      print "Didn't get ack?"
      hexdump(ret)

  def disable(self, port):
    print "disabling", port
    # 03 03 3F E1 59 10 07
    #
    # name: ' ' * 10
    # 20 20 20 20 20 20 20 20 20 20
    #
    packet = [int(x, 16) for x in "03 03 3F E0 59 10 07".split()]
    packet[1] = port - 1
    packet = struct.pack('B' * len(packet), *packet)
    name = self.ports[port].name
    if len(name) < 10:
      name = name + ' ' * (10 - len(name))
    packet += name
    hexdump(packet)
    self.send(packet)
    ret = self.recv(2)
    if ret != "\x03\x00":
      print "Didn't get ack?"
      hexdump(ret)

  def nameport(self, port, name):
    if len(name) > 10:
      print "name " + name + " too long"
      return
    packet = [int(x, 16) for x in "03 03 3F E0 59 10 07".split()]
    packet[1] = port - 1
    packet[3] = 0xe0 | self.ports[port].state
    packet = struct.pack('B' * len(packet), *packet)
    if len(name) < 10:
      name = name + ' ' * (10 - len(name))
    packet += name
    hexdump(packet)
    self.send(packet)
    ret = self.recv(2)
    if ret != "\x03\x00":
      print "Didn't get ack?"
      hexdump(ret)

  def save(self):
    # WRITE 4: 09 53 00 5C
    # READ 4: 09 00 00 09 
    packet = struct.pack('BB', 9, 0x53)
    self.send(packet)
    ret = self.recv(2)
    if ret != "\x09\x00":
      print "Didn't get ack?"
      hexdump(ret)
      

  def unpacket(self, packet):
    type = struct.unpack('B', packet[0:1])[0]
    cksum = self.cksum(packet[:-2])

    if cksum != struct.unpack('>H', packet[-2:])[0]:
      print hex(cksum), hex(struct.unpack('>H', packet[-2:])[0])
      print "cksum missmatch?!?"
      hexdump(packet)
      print hex(cksum)
    else:
      if type == 5:
        packet = packet[1:]

        if struct.unpack('B', packet[0])[0] != 0:
          print "odd packet"
          hexdump(packet)
        packet = packet[1:]

        port = struct.unpack('B', packet[0])[0] + 1
        packet = packet[1:]

        packet = packet[:-2]
        
        setting = struct.unpack('B', packet[0])[0]
        settings = 'disabled'
        if setting & 1:
          settings = "enabled"

        if setting == 0:
          settings = "not present"
        if setting == 0xe0:
          settings = "disabled"

#        elif setting == 0xe1:
#          settings = "enabled"
#        elif setting == 0xc1:
#          settings = "enabled"
        
        status = struct.unpack('B', packet[-11])[0]
        status_s = []
        if status & 1:
          status_s.append("WAITING")
#        else:
#          status_s.append("ACTIVE")
          
        if status & 8:
          status_s.append("POWERED")
        else:
          status_s.append("NO POWER")

# port 3  >            < enabled? 0xe1 11100001 <POWERED>
#        00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f
# 0000 : e1 59 10 08 77 01 f8 00 2b 00 00 08             : .Y..w.. +  .    
       
# port 4  >            < enabled? 0xe1 11100001 <WAITING|NO POWER>
#        00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f
# 0000 : e1 59 10 00 00 00 19 00 00 00 00 01             : .Y.   .    .    

        mw = struct.unpack('>H', packet[3:5])[0]
        voltage = struct.unpack('>H', packet[5:7])[0] / 10.0
        ma = struct.unpack('>H', packet[7:9])[0]

        status_s = "|".join(status_s)
        status_s = "<" + status_s + ">"
        
        if setting != 0:
          name = packet[-10:]
          packet = packet[:-10]
          print "port", port, " >", name, "<", settings, hex(setting), tobin(setting), status_s, str(voltage) + "V", str(ma) + "mA", str(mw) + "mW"
          self.ports[port] = Port(name, setting & 1)
          # port with device present:
          # e1 59 10 08 44 01 f8 00 2a 00 00 08
          # e1 59 10 00 00 00 18 00 00 00 00 01
          # without:^
          # named port1 with device:
          # c1 3c 28 08 77 01 f8 00 2b 00 00 08
          # c1 3c 28 00 00 00 17 00 00 00 00 01
          # without:^
#          hexdump(packet)
        else:
          pass
#          print port, settings
          
        
#              00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f
#       0000 : 05 00 00 c1 3c 28 00 00 00 18 00 00 00 00 01 70 : .  .<(   .    .p
#       0010 : 6f 72 74 31 20 20 20 20 20                      : ort1            
       
#      if type == 3:
#        packet = packet[1:]
#        port = struct.unpack('B', packet[0])[0]
#        print "port2:", port
#        packet = packet[1:]
      elif type == 8:
        packet = packet[1:]
        packet = packet[:-2]

        if struct.unpack('B', packet[0])[0] != 0:
          print "odd packet"
          hexdump(packet)
        packet = packet[1:]

        port = struct.unpack('B', packet[0])[0] + 1
        packet = packet[1:]

        thing = struct.unpack('>H', packet[:2])[0]
        
        bits = struct.unpack('B' * 8, packet[2:-1])
        if bits != (0, 0, 0, 0, 0, 0, 0, 0):
          print "odd bits from packet 8!"
          print bits
          hexdump(packet)

        status = struct.unpack('B' ,packet[-1])[0]
        status_s = ''
        if status == 0:
          status_s = "not ready"
        elif status == 1:
          status_s = "ready"
        if thing != 0 and status != 0:
          print "port:", port, status_s, thing
#        hexdump(packet)
      elif type == 4:
        packet = packet[:-2]
#        hexdump(packet[:-2])
        self.name = packet[-10:]    
      else:
        print "type:", type
        hexdump(packet[:-2])
        print "-" * 20

# possible command string?:
#
# set name
#     
# > 02 03 01 90 01 90 01 90 48 65 6c 6c 6f 20 20 20 20 20 04 4c
#                            H  e  l  l  o
# < 02 00 00 02

#
# blank name
#
#IRP_MJ_WRITE	Serial2	SUCCESS	Length 20: 02 03 00 00 00 00 00 00 20 20 20 20 20 20 20 20 20 20 01 45 	
#IRP_MJ_READ	Serial2	SUCCESS	Length 4: 02 00 00 02 	

#

#
#


#
# 9 54 0 5d <- write flash?!?
#
      
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Control a Phihong POE370U.')

  parser.add_argument('--enable', type=int, nargs=1, metavar=('<port>'),
      help='enable a port')

  parser.add_argument('--disable', type=int, nargs=1, metavar=('<port>'),
      help='disable a port')

  parser.add_argument('--nameport', type=str, nargs=2, metavar=('<port>', '<name>'),
      help='name a port, max 10 letters')

  parser.add_argument('--save', action='store_true',
      help='Save current settings to flash')

  # name a port
  # name the device

  args = parser.parse_args()
  
  p = Phihong()
  p.status()
  p.otherstatus()

  if args.enable:
    p.enable(args.enable[0])
    sys.exit(0)

  if args.disable:
    p.disable(args.disable[0])
    sys.exit(0)

  if args.nameport:
    p.nameport(int(args.nameport[0]), args.nameport[1])
    
  if args.save:
    p.save()
