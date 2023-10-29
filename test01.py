
import sys
import time
from queue import Queue

from scapy import all as cap
from scapy.all import IP
from scapy.all import Padding
from scapy.all import Raw
from scapy.utils import hexdump
from scapy.arch.common import compile_filter

from PySide6 import QtWidgets
from PySide6 import QtGui
from PySide6 import QtCore
from PySide6.QtWidgets import QTableWidgetItem as QTItem
from PySide6.QtWidgets import QListWidgetItem as QLItem
from PySide6.QtWidgets import QTreeWidgetItem as QRItem

from PySide6.QtWidgets import QMainWindow
import s as main_ui

from logger import logger


MAXSIZE = 1024


class Signal(QtCore.QObject):

    recv = QtCore.Signal(None)


class MainWindow(QMainWindow):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.ui = main_ui.Ui_MainWindow()
        self.ui.setupUi(self)

        self.sniffer = None
        self.counter = 0
        self.start_time = 0
        self.signal = Signal()
        self.queue = Queue()
        self.about = None

        self.setWindowTitle(f"Sniffer")

        self.init_interfaces()

    def init_interfaces(self):
        for face in cap.get_working_ifaces():
            self.ui.interfaceBox.addItem(face.name)



        self.ui.startButton.clicked.connect(self.start_click)


        self.ui.packetTable.horizontalHeader().setStretchLastSection(True)
        self.ui.packetTable.cellPressed.connect(self.update_content)
        self.ui.treeWidget.itemPressed.connect(self.update_layer_content)
        self.signal.recv.connect(self.update_packet)



    def get_iface(self):
        idx = self.ui.interfaceBox.currentIndex()
        iface = cap.get_working_ifaces()[idx]
        return iface




    def get_packet_layers(self, packet):
        counter = 0
        while True:
            layer = packet.getlayer(counter)
            if layer is None:
                break
            yield layer
            counter += 1

    def update_layer_content(self, item, column):
        if not hasattr(item, 'layer'):
            return
        layer = item.layer
        self.ui.contentEdit.setText(hexdump(layer, dump=True))

    def update_content(self, x, y):
        logger.debug("%s.ui, %s.ui clicked", x, y)
        item = self.ui.packetTable.item(x, 6)
        if not hasattr(item, 'packet'):
            return
        logger.debug(item)
        logger.debug(item.text())
        packet = item.packet
        self.ui.contentEdit.setText(hexdump(packet, dump=True))

        self.ui.treeWidget.clear()
        for layer in self.get_packet_layers(packet):
            item = QRItem(self.ui.treeWidget)
            item.layer = layer
            item.setText(0, layer.name)


            for name, value in layer.fields.items():
                child = QRItem(item)
                child.setText(0, f"{name}: {value}")



    def update_packet(self):
        packet = self.queue.get(False)
        if not packet:
            return

        if self.ui.packetTable.rowCount() >= MAXSIZE:
            self.ui.packetTable.removeRow(0)

        row = self.ui.packetTable.rowCount()
        self.ui.packetTable.insertRow(row)

        # No.
        self.counter += 1
        self.ui.packetTable.setItem(row, 0, QTItem(str(self.counter)))

        # Time
        elapse = time.time() - self.start_time
        self.ui.packetTable.setItem(row, 1, QTItem(f"{elapse:2f}"))

        # source
        if IP in packet:
            src = packet[IP].src
            dst = packet[IP].dst
        else:
            src = packet.src
            dst = packet.dst

        self.ui.packetTable.setItem(row, 2, QTItem(src))

        # destination
        self.ui.packetTable.setItem(row, 3, QTItem(dst))

        # protocol

        layer = None
        for var in self.get_packet_layers(packet):
            if not isinstance(var, (Padding, Raw)):
                layer = var

        protocol = layer.name
        self.ui.packetTable.setItem(row, 4, QTItem(str(protocol)))

        # length
        length = f"{len(packet)}"
        self.ui.packetTable.setItem(row, 5, QTItem(length))

        # info

        info = str(packet.summary())
        item = QTItem(info)
        item.packet = packet
        self.ui.packetTable.setItem(row, 6, item)


    def sniff_action(self, packet):
        if not self.sniffer:
            return

        self.queue.put(packet)
        self.signal.recv.emit()

    def start_click(self):
        logger.debug("start button was clicked")
        if self.sniffer:
            self.sniffer.stop()
            self.sniffer = None
            self.ui.startButton.setText("开始")
            self.ui.interfaceBox.setEnabled(True)
            self.ui.filterEdit.setEnabled(True)
            return

        exp = self.ui.filterEdit.text()
        logger.debug("filter expression %s.ui", exp)

        iface = self.get_iface()
        logger.debug("sniffing interface %s.ui", iface)

        self.sniffer = cap.AsyncSniffer(
            iface=iface,
            prn=self.sniff_action,
            filter=exp,
        )

        self.sniffer.start()
        self.counter = 0
        self.start_time = time.time()

        self.ui.startButton.setText("停止")
        self.ui.interfaceBox.setEnabled(False)
        self.ui.filterEdit.setEnabled(False)
        self.ui.packetTable.clearContents()
        self.ui.packetTable.setRowCount(0)
        self.ui.treeWidget.clear()
        self.ui.contentEdit.clear()





if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
