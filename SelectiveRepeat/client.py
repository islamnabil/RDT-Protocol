#!/usr/bin/python


import os
import math
import logging
import random
import socket
import struct
import select
import hashlib
from collections import namedtuple
from collections import OrderedDict
from threading import Thread


# Set logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s RECEIVER [%(levelname)s] %(message)s',)
log = logging.getLogger()


class SocketError(Exception):
    pass


class FileIOError(Exception):
    pass


class WindowSizeError(Exception):
    pass


class Receiver(object):
    """
    Receiver running Selective Repeat protocol for reliable data transfer.
    """

    def __init__(self,
                 receiverIP="127.0.0.1",
                 receiverPort=8080,senderIP="localhost",
                 senderPort=10000,
                 sequenceNumberBits=2,
                 windowSize=2,                   
                 www=os.path.join(os.getcwd(), "data", "receiver")):
        self.receiverIP = receiverIP
        self.receiverPort = receiverPort
        self.sequenceNumberBits = sequenceNumberBits
        self.windowSize = windowSize
        self.www = www

    def open(self):
        """
        Create UDP socket for communication with the Server.
        """
        log.info("Creating UDP socket %s:%d for communication with the Server",
                 self.receiverIP, self.receiverPort)
       
        # server_address = ('127.0.0.1', 8081)
        # self.receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # # self.receiverSocket.sendto('MyName', server_address )
        # log.info("IAM HEEERE")

        
        # self.receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.receiverSocket.bind((self.receiverIP, self.receiverPort))
        #fileName = raw_input('File Name :')
        #self.receiverSocket.sendto(fileName, ('localhost',10000))
           # self.receiverSocket.setblocking(0)
        # except Exception as e:
        #     log.error("Could not create UDP socket for communication with the client!")
        #     log.debug(e)
        #     raise SocketError("Creating UDP socket %s:%d for communication with the client failed!"
        #                    % (self.receiverIP, self.receiverPort))

    def receive(self,
                filename,
                senderIP="localhost",
                senderPort=10000,receiverIP="127.0.0.1",
                receiverPort=8080,
                timeout=10):
        
        self.SendeIP = senderIP
        self.senderPort = senderPort
        """
        Create UDP socket for communication with the Server.
        """
        log.info("Creating UDP socket %s:%d for communication with the Server",
                 self.receiverIP, self.receiverPort)
        self.receiverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiverSocket.bind((self.receiverIP, self.receiverPort))
        """
        Receive packets transmitted from sender and
        write payload data to the specified file.
        """
        log.info("Started to receive packets transmitted from sender")
        filenamePath = os.path.join(self.www, filename)
        
        self.receiverSocket.sendto(filename, (self.SendeIP,self.senderPort))
        # Create a file handler for writing data received from sender
        try:
            log.info("Writing payload data to '%s'", filenamePath)
            self.fileHandle = open(filenamePath, "wb")
        except IOError as e:
            log.error("Could not create a file handle!")
            log.debug(e)
            raise FileIOError("Creating a file handle failed!\nFilename: %s"
                              % filenamePath)

        # Create an object of 'Window', which handles packet receipt
        window = Window(self.sequenceNumberBits,
                        self.windowSize)

        # Create a thread named 'PacketHandler' to monitor packet receipt
        log.info("Creating a thread to monitor packet receipt")
        packetHandler = PacketHandler(self.fileHandle,
                                      self.receiverSocket,
                                      senderIP,
                                      senderPort,
                                      self.receiverIP,
                                      self.receiverPort,
                                      window,
                                      timeout)

        # Start thread execution
        log.info("Starting thread execution")
        packetHandler.start()

        # Wait for a thread to finish its execution
        packetHandler.join()

    def close(self):
        """
        Close a file handle and UDP socket.
        """
        # Close file handle
        try:
            if self.fileHandle:
                self.fileHandle.close()
        except IOError as e:
            log.error("Could not close a file handle!")
            log.debug(e)
            raise FileIOError("Closing a file handle failed!")

        # Close receiver's socket
        try:
            if self.receiverSocket:
                self.receiverSocket.close()
        except Exception as e:
            log.error("Could not close UDP socket!")
            log.debug(e)
            raise SocketError("Closing UDP socket %s:%d failed!"
                              % (self.receiverIP, self.receiverPort))


class Window(object):
    """
    Class for assisting packet receipt.
    """

    def __init__(self, sequenceNumberBits, windowSize=None):
        self.expectedPkt = 0
        self.maxSequenceSpace = int(math.pow(2, sequenceNumberBits))
        if windowSize is None:
            self.maxWindowSize = int(math.pow(2, sequenceNumberBits-1))
        else:
            if windowSize > int(math.pow(2, sequenceNumberBits-1)):
                raise WindowSizeError("Invalid window size!!")
            else:
                self.maxWindowSize = windowSize
        self.lastPkt = self.maxWindowSize - 1
        self.receiptWindow = OrderedDict()
        self.isPacketReceipt = False

    def expectedPacket(self):
        return self.expectedPkt

    def lastPacket(self):
        return self.lastPkt

    def out_of_order(self, key):
        if self.expectedPacket() > self.lastPacket():
            if key < self.expectedPacket() and key > self.lastPacket():
                return True
        else:
            if key < self.expectedPacket() or key > self.lastPacket():
                return True
        return False

    def exist(self, key):
        if key in self.receiptWindow and self.receiptWindow[key] != None:
            return True
        return False

    def store(self, receivedPacket):
        if not self.expected(receivedPacket.SequenceNumber):
            sequenceNumber = self.expectedPkt

            while sequenceNumber != receivedPacket.SequenceNumber:
                if sequenceNumber not in self.receiptWindow:
                    self.receiptWindow[sequenceNumber] = None

                sequenceNumber += 1
                if sequenceNumber >= self.maxSequenceSpace:
                    sequenceNumber %= self.maxSequenceSpace

        self.receiptWindow[receivedPacket.SequenceNumber] = receivedPacket

    def expected(self, sequenceNumber):
        if sequenceNumber == self.expectedPkt:
            return True
        return False

    def next(self):
        packet = None

        if len(self.receiptWindow) > 0:
            nextPkt = self.receiptWindow.items()[0]

            if nextPkt[1] != None:
                packet = nextPkt[1]

                del self.receiptWindow[nextPkt[0]]

                self.expectedPkt = nextPkt[0] + 1
                if self.expectedPkt >= self.maxSequenceSpace:
                    self.expectedPkt %= self.maxSequenceSpace

                self.lastPkt = self.expectedPkt + self.maxWindowSize - 1
                if self.lastPkt >= self.maxSequenceSpace:
                    self.lastPkt %= self.maxSequenceSpace

        return packet

    def receipt(self):
        return self.isPacketReceipt

    def start_receipt(self):
        self.isPacketReceipt = True


class PacketHandler(Thread):
    """
    Thread for monitoring packet receipt.
    """

    PACKET = namedtuple("Packet", ["SequenceNumber", "Checksum", "Data"])
    ACK = namedtuple("ACK", ["AckNumber", "Checksum"])

    def __init__(self,
                 fileHandle,
                 receiverSocket,
                 senderIP,
                 senderPort,
                 receiverIP,
                 receiverPort,
                 window,
                 timeout=10,
                 packetLossProbability=0.1,
                 bufferSize=2048):
        Thread.__init__(self)
        self.fileHandle = fileHandle
        self.receiverSocket = receiverSocket
        self.senderIP = senderIP
        self.senderPort = senderPort
        self.receiverIP = receiverIP
        self.receiverPort = receiverPort
        self.window = window
        self.timeout = timeout
        self.packetLossProbability = packetLossProbability
        self.bufferSize = bufferSize

    def run(self):
        """
        Start monitoring packet receipt.
        """
        log.info("Started to monitor packet receipt")

        # Monitor receiver
        # untill all packets are successfully received from sender
        chance = 0
        while True:
            # Listen for incoming packets on receiver's socket
            # with the provided timeout
            ready = select.select([self.receiverSocket], [], [], self.timeout)

            # If no packet is received within timeout;
            if not ready[0]:
                # Wait, if no packets are yet transmitted by sender
                if not self.window.receipt():
                    continue
                # Stop receiving packets from sender,
                # if there are more than 5 consecutive timeouts
                else:
                    if chance == 1:
                        #log.warning("Timeout!!")
                        #log.info("Gracefully terminating the receiver process, as Server stopped transmission!!")
                        log.info("File Received!")
                        break
                    else:
                        chance += 1
                        continue
            else:
                chance = 0
                if not self.window.receipt():
                    self.window.start_receipt()

            # Receive packet
            try:
                receivedPacket, _ = self.receiverSocket.recvfrom(self.bufferSize)
            except Exception as e:
                log.error("Could not receive UDP packet!")
                log.debug(e)
                raise SocketError("Receiving UDP packet failed!")

            # Parse header fields and payload data from the received packet
            receivedPacket = self.parse(receivedPacket)

            # Check whether the received packet is not corrupt
            if self.corrupt(receivedPacket):
                log.warning("Received corrupt packet!!")
                log.warning("Discarding packet with sequence number: %d",
                            receivedPacket.SequenceNumber)
                continue

            # If the received packet has out of order sequence number,
            # then discard the received packet and
            # send the corresponding acknowledgement
            if self.window.out_of_order(receivedPacket.SequenceNumber):
                log.warning("Received packet outside receipt window!!")
                log.warning("Discarding packet with sequence number: %d",
                            receivedPacket.SequenceNumber)

                # Reliable acknowledgement transfer
                log.info("Transmitting an acknowledgement with ack number: %d",
                         receivedPacket.SequenceNumber)
                self.rdt_send(receivedPacket.SequenceNumber)

                continue

            # Simulate artificial packet loss
            if self.simulate_packet_loss():
                log.error("Simulating artificial packet loss!!")
                log.error("Lost a packet with sequence number: %d",
                          receivedPacket.SequenceNumber)
                continue

            # If received packet is duplicate, then discard it
            if self.window.exist(receivedPacket.SequenceNumber):
                log.warning("Received duplicate packet!!")
                log.warning("Discarding packet with sequence number: %d",
                            receivedPacket.SequenceNumber)
                continue
            # Otherwise, store received packet into receipt window and
            # send corresponding acknowledgement
            else:
                log.info("Received packet with sequence number: %d",
                         receivedPacket.SequenceNumber)

                self.window.store(receivedPacket)

                log.info("Transmitting an acknowledgement with ack number: %d",
                         receivedPacket.SequenceNumber)
                self.rdt_send(receivedPacket.SequenceNumber)

            # If sequence number of received packet matches with the expected packet,
            # then deliver the packet and all consecutive previously arrived &
            # stored packets to Application Layer
            if self.window.expected(receivedPacket.SequenceNumber):
                self.deliver_packets()

    def parse(self, receivedPacket):
        """
        Parse header fields and payload data from the received packet.
        """
        header = receivedPacket[0:6]
        data = receivedPacket[6:]

        sequenceNumber = struct.unpack('=I', header[0:4])[0]
        checksum = struct.unpack('=H', header[4:])[0]

        packet = PacketHandler.PACKET(SequenceNumber=sequenceNumber,
                                      Checksum=checksum,
                                      Data=data)

        return packet

    def corrupt(self, receivedPacket):
        """
        Check whether the received packet is corrupt or not.
        """
        # Compute checksum for the received packet
        computedChecksum = self.checksum(receivedPacket.Data)

        # Compare computed checksum with the checksum of received packet
        if computedChecksum != receivedPacket.Checksum:
            return True
        else:
            return False

    def checksum(self, data):
        """
        Compute and return a checksum of the given payload data
        """
        # Force payload data into 16 bit chunks
        if (len(data) % 2) != 0:
            data += "0"

        sum = 0
        for i in range(0, len(data), 2):
            data16 = ord(data[i]) + (ord(data[i+1]) << 8)
            sum = self.carry_around_add(sum, data16)

        return ~sum & 0xffff

    def carry_around_add(self, sum, data16):
        """
        Helper function for carry around add.
        """
        sum = sum + data16
        return (sum & 0xffff) + (sum >> 16)

    def rdt_send(self, ackNumber):
        """
        Reliable acknowledgement transfer.
        """
        ack = PacketHandler.ACK(AckNumber=ackNumber,
                                Checksum=self.get_hashcode(ackNumber))

        # Create a raw acknowledgement
        rawAck = self.make_pkt(ack)

        # Transmit an acknowledgement using underlying UDP protocol
        self.udt_send(rawAck)

    def get_hashcode(self, data):
        """
        Compute the hash code.
        """
        hashcode = hashlib.md5()
        hashcode.update(str(data))
        return hashcode.digest()

    def make_pkt(self, ack):
        """
        Create a raw acknowledgement.
        """
        ackNumber = struct.pack('=I', ack.AckNumber)
        checksum = struct.pack('=16s', ack.Checksum)
        rawAck = ackNumber + checksum
        return rawAck

    def udt_send(self, ack):
        """
        Transmit an acknowledgement using underlying UDP protocol.
        """
        try:
            self.receiverSocket.sendto(ack, (self.senderIP, self.senderPort))
        except Exception as e:
            log.error("Could not send UDP packet!")
            log.debug(e)
            raise SocketError("Sending UDP packet to %s:%d failed!"
                              % (self.senderIP, self.senderPort))

    def simulate_packet_loss(self):
        """
        Simulate artificial packet loss.
        """
        r = random.random()

        if r <= self.packetLossProbability:
            return True
        else:
            return False

    def deliver_packets(self):
        """
        Deliver packets to Application Layer.
        """
        while True:
            # Get the next packet to be delivered to Application Layer
            packet = self.window.next()

            # If next packet is available for delivery,
            # then deliver data to Application Layer
            if packet:
                log.info("Delivered packet with sequence number: %d",
                         packet.SequenceNumber)
                self.deliver(packet.Data)
            else:
                break

    def deliver(self, data):
        """
        Deliver data to Application Layer.
        """
        try:
            self.fileHandle.write(data)
        except IOError as e:
            log.error("Could not write to file handle!")
            log.debug(e)
            raise FileIOError("Writing to file handle failed!")
