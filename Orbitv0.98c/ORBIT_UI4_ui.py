# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ORBIT_UI4.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFrame,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QSizePolicy,
    QSlider, QSpacerItem, QSplitter, QStackedWidget,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget)
import Orbit_rc
import Orbit_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1150, 920)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        MainWindow.setStyleSheet(u"/* Existing styles */\n"
"background-color: rgb(0, 64, 122);\n"
"\n"
"QPushButton {\n"
"    background-color: rgb(139, 139, 139); /* Gray background */\n"
"    color: white;                         /* White text */\n"
"    border-style: solid;\n"
"    border-width: 2px;\n"
"    border-color: #4CAF50;\n"
"    border-radius: 10px;                  /* Rounded corners */\n"
"    padding: 10px;\n"
"    font-size: 16px;\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: #00407A;            /* Darker green background on hover */\n"
"}\n"
"QTabWidget::pane { /* The tab widget frame */\n"
"    border-top: 2px solid #C2C7CB;\n"
"    position: absolute;\n"
"    top: -0.5em;\n"
"    color: #333333;\n"
"    background-color: #f0f0f0;\n"
"    border-radius: 5px;\n"
"}\n"
"QTabBar::tab {\n"
"    background: #E1E1E1;\n"
"    border: 2px solid #C4C4C3;\n"
"    border-bottom-color: #C2C7CB; /* Same as pane color */\n"
"    border-top-left-radius: 4px;\n"
"    border-top-right-radius: 4px;\n"
"    padding: 5px;\n"
"}\n"
"QT"
                        "abBar::tab:selected, QTabBar::tab:hover {\n"
"    background: #fafafa;\n"
"}\n"
"\n"
"/* Added styles for QDockWidget */\n"
"QDockWidget {\n"
"    border: 1px solid #d3d3d3; /* Light gray border */\n"
"    border-radius: 5px;        /* Rounded corners */\n"
"    background-color: rgba(255, 255, 255, 0.9); /* White background with slight transparency */\n"
"    titlebar-close-icon: url(close.png);\n"
"    titlebar-normal-icon: url(undock.png);\n"
"}\n"
"QDockWidget::title {\n"
"    text-align: left;          /* Aligns title text to the left */\n"
"    background-color: rgba(0, 64, 122, 0.85); /* Slightly transparent background for the title */\n"
"    padding: 5px;\n"
"    border-radius: 5px 5px 0 0; /* Rounded corners on the top */\n"
"}\n"
"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"\n"
"/* QSplitter styles */\n"
"QSplitter::handle {\n"
"    background-color: #54BCEB;\n"
"    border: 1px solid #54BCEB;\n"
"    border-radius: 1px;\n"
""
                        "}\n"
"QSplitter::handle:hover {\n"
"    background-color: #54BCEB;\n"
"}\n"
"\n"
"")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setStyleSheet(u"")
        self.mainHorizontalLayout = QHBoxLayout(self.centralwidget)
        self.mainHorizontalLayout.setSpacing(0)
        self.mainHorizontalLayout.setObjectName(u"mainHorizontalLayout")
        self.mainHorizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.leftPanelLayout = QVBoxLayout()
        self.leftPanelLayout.setObjectName(u"leftPanelLayout")
        self.leftPanelStackedWidget = QStackedWidget(self.centralwidget)
        self.leftPanelStackedWidget.setObjectName(u"leftPanelStackedWidget")
        self.leftPanelStackedWidget.setStyleSheet(u"QTabWidget::pane { /* The tab widget frame */\n"
"    border-top: 2px solid #C2C7CB;\n"
"    position: absolute;\n"
"    top: -0.5em;\n"
"    color: #333333;\n"
"    background-color: #f0f0f0;\n"
"    border-radius: 5px;\n"
"}\n"
"QTabBar::tab {\n"
"    background: #E1E1E1;\n"
"    border: 2px solid #C4C4C3;\n"
"    border-bottom-color: #C2C7CB; /* Same as pane color */\n"
"    border-top-left-radius: 4px;\n"
"    border-top-right-radius: 4px;\n"
"    padding: 5px;\n"
"}\n"
"\n"
"QTabBar::tab:selected {\n"
"    background: #2e8b57; /* New distinct color for active tab */\n"
"    color: white;\n"
"    border-color: #2e8b57; /* Optional: change the border color to match */\n"
"}\n"
"\n"
"\n"
"\n"
"QPushButton {\n"
"    border-style: solid;\n"
"    border-width: 2px;\n"
"    border-color: #54BCEB;                /* New button border color */\n"
"    border-radius: 10px;                  /* Rounded corners */\n"
"    background-color: transparent;        /* Transparent background */\n"
"    color: white;          "
                        "               /* White text */\n"
"    padding: 10px;\n"
"    font-size: 16px;\n"
"}\n"
"QPushButton:disabled {\n"
"    background-color: #676767;            /* Disabled button color */\n"
"    border-color: #8B8B8B;                /* Disabled button border color */\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: #00407A;            /* Dark blue background on hover */\n"
"}\n"
"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"QLabel {\n"
"    color: white;\n"
"	font-size: 12px\n"
"}")
        self.tab0ButtonsPage = QWidget()
        self.tab0ButtonsPage.setObjectName(u"tab0ButtonsPage")
        self.tab0Layout = QVBoxLayout(self.tab0ButtonsPage)
        self.tab0Layout.setObjectName(u"tab0Layout")
        self.tab0Label = QLabel(self.tab0ButtonsPage)
        self.tab0Label.setObjectName(u"tab0Label")
        self.tab0Label.setAlignment(Qt.AlignCenter)

        self.tab0Layout.addWidget(self.tab0Label)

        self.line_4 = QFrame(self.tab0ButtonsPage)
        self.line_4.setObjectName(u"line_4")
        self.line_4.setFrameShape(QFrame.Shape.HLine)
        self.line_4.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab0Layout.addWidget(self.line_4)

        self.label = QLabel(self.tab0ButtonsPage)
        self.label.setObjectName(u"label")
        self.label.setStyleSheet(u"QLabel {\n"
"    background-color: #40C4FF;\n"
"    border: none;\n"
"}")
        self.label.setPixmap(QPixmap(u":/icons/icons/Sponsors.png"))

        self.tab0Layout.addWidget(self.label)

        self.line_14 = QFrame(self.tab0ButtonsPage)
        self.line_14.setObjectName(u"line_14")
        self.line_14.setFrameShape(QFrame.Shape.HLine)
        self.line_14.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab0Layout.addWidget(self.line_14)

        self.btn_tab0_ImportDirectory = QPushButton(self.tab0ButtonsPage)
        self.btn_tab0_ImportDirectory.setObjectName(u"btn_tab0_ImportDirectory")

        self.tab0Layout.addWidget(self.btn_tab0_ImportDirectory)

        self.textEdit = QTextEdit(self.tab0ButtonsPage)
        self.textEdit.setObjectName(u"textEdit")
        self.textEdit.setEnabled(True)
        self.textEdit.setStyleSheet(u"QTextEdit {\n"
"    border: none;\n"
"    background: transparent;\n"
"}")
        self.textEdit.setReadOnly(True)

        self.tab0Layout.addWidget(self.textEdit)

        self.btn_tab0_LoadBridgeData = QPushButton(self.tab0ButtonsPage)
        self.btn_tab0_LoadBridgeData.setObjectName(u"btn_tab0_LoadBridgeData")
        self.btn_tab0_LoadBridgeData.setEnabled(True)
        self.btn_tab0_LoadBridgeData.setStyleSheet(u"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"")

        self.tab0Layout.addWidget(self.btn_tab0_LoadBridgeData)

        self.btn_tab0_updateData = QPushButton(self.tab0ButtonsPage)
        self.btn_tab0_updateData.setObjectName(u"btn_tab0_updateData")
        self.btn_tab0_updateData.setEnabled(True)
        self.btn_tab0_updateData.setStyleSheet(u"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"")

        self.tab0Layout.addWidget(self.btn_tab0_updateData)

        self.btn_tab0_ConfirmProjectData = QPushButton(self.tab0ButtonsPage)
        self.btn_tab0_ConfirmProjectData.setObjectName(u"btn_tab0_ConfirmProjectData")
        self.btn_tab0_ConfirmProjectData.setEnabled(True)
        self.btn_tab0_ConfirmProjectData.setStyleSheet(u"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"")

        self.tab0Layout.addWidget(self.btn_tab0_ConfirmProjectData)

        self.leftPanelStackedWidget.addWidget(self.tab0ButtonsPage)
        self.tab1ButtonsPage = QWidget()
        self.tab1ButtonsPage.setObjectName(u"tab1ButtonsPage")
        self.tab1Layout = QVBoxLayout(self.tab1ButtonsPage)
        self.tab1Layout.setObjectName(u"tab1Layout")
        self.tab1Label = QLabel(self.tab1ButtonsPage)
        self.tab1Label.setObjectName(u"tab1Label")
        self.tab1Label.setLayoutDirection(Qt.LeftToRight)
        self.tab1Label.setAlignment(Qt.AlignCenter)

        self.tab1Layout.addWidget(self.tab1Label)

        self.line_3 = QFrame(self.tab1ButtonsPage)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.HLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab1Layout.addWidget(self.line_3)

        self.label_2 = QLabel(self.tab1ButtonsPage)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setPixmap(QPixmap(u":/icons/icons/Sponsors.png"))

        self.tab1Layout.addWidget(self.label_2)

        self.line_12 = QFrame(self.tab1ButtonsPage)
        self.line_12.setObjectName(u"line_12")
        self.line_12.setFrameShape(QFrame.Shape.HLine)
        self.line_12.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab1Layout.addWidget(self.line_12)

        self.trajectoryGroupBox = QGroupBox(self.tab1ButtonsPage)
        self.trajectoryGroupBox.setObjectName(u"trajectoryGroupBox")
        self.trajectoryGroupBox.setStyleSheet(u"QGroupBox { color: white; font-weight: bold; }")
        self.trajectoryLayout = QVBoxLayout(self.trajectoryGroupBox)
        self.trajectoryLayout.setObjectName(u"trajectoryLayout")
        self.btn_tab1_DrawTrajectory = QPushButton(self.trajectoryGroupBox)
        self.btn_tab1_DrawTrajectory.setObjectName(u"btn_tab1_DrawTrajectory")

        self.trajectoryLayout.addWidget(self.btn_tab1_DrawTrajectory)

        self.trajectoryControlsLayout = QHBoxLayout()
        self.trajectoryControlsLayout.setObjectName(u"trajectoryControlsLayout")
        self.btnUndo_trajectory = QPushButton(self.trajectoryGroupBox)
        self.btnUndo_trajectory.setObjectName(u"btnUndo_trajectory")
        self.btnUndo_trajectory.setMaximumSize(QSize(50, 16777215))
        icon = QIcon()
        icon.addFile(u":/icons/icons/Undo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btnUndo_trajectory.setIcon(icon)

        self.trajectoryControlsLayout.addWidget(self.btnUndo_trajectory)

        self.btnRedo_trajectory = QPushButton(self.trajectoryGroupBox)
        self.btnRedo_trajectory.setObjectName(u"btnRedo_trajectory")
        self.btnRedo_trajectory.setMaximumSize(QSize(50, 16777215))
        icon1 = QIcon()
        icon1.addFile(u":/icons/icons/Redo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btnRedo_trajectory.setIcon(icon1)

        self.trajectoryControlsLayout.addWidget(self.btnRedo_trajectory)


        self.trajectoryLayout.addLayout(self.trajectoryControlsLayout)


        self.tab1Layout.addWidget(self.trajectoryGroupBox)

        self.pillarsGroupBox = QGroupBox(self.tab1ButtonsPage)
        self.pillarsGroupBox.setObjectName(u"pillarsGroupBox")
        self.pillarsLayout = QVBoxLayout(self.pillarsGroupBox)
        self.pillarsLayout.setObjectName(u"pillarsLayout")
        self.btn_tab1_mark_pillars = QPushButton(self.pillarsGroupBox)
        self.btn_tab1_mark_pillars.setObjectName(u"btn_tab1_mark_pillars")

        self.pillarsLayout.addWidget(self.btn_tab1_mark_pillars)

        self.trajectoryControlsLayout_2 = QHBoxLayout()
        self.trajectoryControlsLayout_2.setObjectName(u"trajectoryControlsLayout_2")
        self.btnUndo_Pillar = QPushButton(self.pillarsGroupBox)
        self.btnUndo_Pillar.setObjectName(u"btnUndo_Pillar")
        self.btnUndo_Pillar.setMaximumSize(QSize(50, 16777215))
        self.btnUndo_Pillar.setIcon(icon)

        self.trajectoryControlsLayout_2.addWidget(self.btnUndo_Pillar)

        self.btnRedo_Pillar = QPushButton(self.pillarsGroupBox)
        self.btnRedo_Pillar.setObjectName(u"btnRedo_Pillar")
        self.btnRedo_Pillar.setMaximumSize(QSize(50, 16777215))
        self.btnRedo_Pillar.setIcon(icon1)

        self.trajectoryControlsLayout_2.addWidget(self.btnRedo_Pillar)


        self.pillarsLayout.addLayout(self.trajectoryControlsLayout_2)


        self.tab1Layout.addWidget(self.pillarsGroupBox)

        self.safetyZonesGroupBox = QGroupBox(self.tab1ButtonsPage)
        self.safetyZonesGroupBox.setObjectName(u"safetyZonesGroupBox")
        self.safetyZonesLayout = QVBoxLayout(self.safetyZonesGroupBox)
        self.safetyZonesLayout.setObjectName(u"safetyZonesLayout")
        self.btn_tab1_SafetyZones = QPushButton(self.safetyZonesGroupBox)
        self.btn_tab1_SafetyZones.setObjectName(u"btn_tab1_SafetyZones")

        self.safetyZonesLayout.addWidget(self.btn_tab1_SafetyZones)

        self.trajectoryControlsLayout_3 = QHBoxLayout()
        self.trajectoryControlsLayout_3.setObjectName(u"trajectoryControlsLayout_3")
        self.btnLoad_SafetyZones = QPushButton(self.safetyZonesGroupBox)
        self.btnLoad_SafetyZones.setObjectName(u"btnLoad_SafetyZones")
        self.btnLoad_SafetyZones.setMaximumSize(QSize(50, 16777215))
        icon2 = QIcon()
        icon2.addFile(u":/icons/icons/Save.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btnLoad_SafetyZones.setIcon(icon2)

        self.trajectoryControlsLayout_3.addWidget(self.btnLoad_SafetyZones)

        self.btnUndo_Safety = QPushButton(self.safetyZonesGroupBox)
        self.btnUndo_Safety.setObjectName(u"btnUndo_Safety")
        self.btnUndo_Safety.setMaximumSize(QSize(50, 16777215))
        self.btnUndo_Safety.setIcon(icon)

        self.trajectoryControlsLayout_3.addWidget(self.btnUndo_Safety)

        self.btnRedo_Safety = QPushButton(self.safetyZonesGroupBox)
        self.btnRedo_Safety.setObjectName(u"btnRedo_Safety")
        self.btnRedo_Safety.setMaximumSize(QSize(50, 16777215))
        self.btnRedo_Safety.setIcon(icon1)

        self.trajectoryControlsLayout_3.addWidget(self.btnRedo_Safety)

        self.btnAdd_Safety = QPushButton(self.safetyZonesGroupBox)
        self.btnAdd_Safety.setObjectName(u"btnAdd_Safety")
        self.btnAdd_Safety.setMaximumSize(QSize(50, 16777215))
        icon3 = QIcon()
        icon3.addFile(u":/icons/icons/bt_Add_SZ.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.btnAdd_Safety.setIcon(icon3)

        self.trajectoryControlsLayout_3.addWidget(self.btnAdd_Safety)


        self.safetyZonesLayout.addLayout(self.trajectoryControlsLayout_3)

        self.widget = QWidget(self.safetyZonesGroupBox)
        self.widget.setObjectName(u"widget")

        self.safetyZonesLayout.addWidget(self.widget)


        self.tab1Layout.addWidget(self.safetyZonesGroupBox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.tab1Layout.addItem(self.verticalSpacer)

        self.btn_tab1_build_model = QPushButton(self.tab1ButtonsPage)
        self.btn_tab1_build_model.setObjectName(u"btn_tab1_build_model")
        self.btn_tab1_build_model.setEnabled(True)
        self.btn_tab1_build_model.setStyleSheet(u"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"")

        self.tab1Layout.addWidget(self.btn_tab1_build_model)

        self.leftPanelStackedWidget.addWidget(self.tab1ButtonsPage)
        self.tab2ButtonsPage = QWidget()
        self.tab2ButtonsPage.setObjectName(u"tab2ButtonsPage")
        self.tab2Layout = QVBoxLayout(self.tab2ButtonsPage)
        self.tab2Layout.setObjectName(u"tab2Layout")
        self.tab2Label = QLabel(self.tab2ButtonsPage)
        self.tab2Label.setObjectName(u"tab2Label")
        self.tab2Label.setAlignment(Qt.AlignCenter)

        self.tab2Layout.addWidget(self.tab2Label)

        self.line_2 = QFrame(self.tab2ButtonsPage)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.HLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab2Layout.addWidget(self.line_2)

        self.label_3 = QLabel(self.tab2ButtonsPage)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setPixmap(QPixmap(u":/icons/icons/Sponsors.png"))

        self.tab2Layout.addWidget(self.label_3)

        self.line_13 = QFrame(self.tab2ButtonsPage)
        self.line_13.setObjectName(u"line_13")
        self.line_13.setFrameShape(QFrame.Shape.HLine)
        self.line_13.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab2Layout.addWidget(self.line_13)

        self.btn_tab2_TopView = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_TopView.setObjectName(u"btn_tab2_TopView")

        self.tab2Layout.addWidget(self.btn_tab2_TopView)

        self.line_5 = QFrame(self.tab2ButtonsPage)
        self.line_5.setObjectName(u"line_5")
        self.line_5.setFrameShape(QFrame.Shape.HLine)
        self.line_5.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab2Layout.addWidget(self.line_5)

        self.btn_tab2_UpdateSafetyZones = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_UpdateSafetyZones.setObjectName(u"btn_tab2_UpdateSafetyZones")

        self.tab2Layout.addWidget(self.btn_tab2_UpdateSafetyZones)

        self.btn_tab2_LoadPC = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_LoadPC.setObjectName(u"btn_tab2_LoadPC")

        self.tab2Layout.addWidget(self.btn_tab2_LoadPC)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.tab2Layout.addItem(self.horizontalSpacer_2)

        self.line_11 = QFrame(self.tab2ButtonsPage)
        self.line_11.setObjectName(u"line_11")
        self.line_11.setFrameShape(QFrame.Shape.HLine)
        self.line_11.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab2Layout.addWidget(self.line_11)

        self.btn_tab2_Dock_updateOverviewFlight = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_Dock_updateOverviewFlight.setObjectName(u"btn_tab2_Dock_updateOverviewFlight")
        self.btn_tab2_Dock_updateOverviewFlight.setEnabled(True)
        self.btn_tab2_Dock_updateOverviewFlight.setStyleSheet(u"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"")

        self.tab2Layout.addWidget(self.btn_tab2_Dock_updateOverviewFlight)

        self.btn_tab2_Dock_updateInspectionRoute = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_Dock_updateInspectionRoute.setObjectName(u"btn_tab2_Dock_updateInspectionRoute")
        self.btn_tab2_Dock_updateInspectionRoute.setEnabled(True)
        self.btn_tab2_Dock_updateInspectionRoute.setStyleSheet(u"\n"
"QToolTip {\n"
"    color: white;\n"
"    background-color:rgb(0, 64, 122);\n"
"    border: 1px solid white;\n"
"}\n"
"")

        self.tab2Layout.addWidget(self.btn_tab2_Dock_updateInspectionRoute)

        self.line_10 = QFrame(self.tab2ButtonsPage)
        self.line_10.setObjectName(u"line_10")
        self.line_10.setFrameShape(QFrame.Shape.HLine)
        self.line_10.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab2Layout.addWidget(self.line_10)

        self.WaypointsTextBox = QTextEdit(self.tab2ButtonsPage)
        self.WaypointsTextBox.setObjectName(u"WaypointsTextBox")
        self.WaypointsTextBox.setStyleSheet(u"QTextEdit {\n"
"    border: none;\n"
"    background: transparent;\n"
"}")
        self.WaypointsTextBox.setReadOnly(True)

        self.tab2Layout.addWidget(self.WaypointsTextBox)

        self.WaypointsSlider = QSlider(self.tab2ButtonsPage)
        self.WaypointsSlider.setObjectName(u"WaypointsSlider")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.WaypointsSlider.sizePolicy().hasHeightForWidth())
        self.WaypointsSlider.setSizePolicy(sizePolicy1)
        self.WaypointsSlider.setOrientation(Qt.Horizontal)
        self.WaypointsSlider.setTickInterval(0)

        self.tab2Layout.addWidget(self.WaypointsSlider)

        self.label_4 = QLabel(self.tab2ButtonsPage)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setLayoutDirection(Qt.LeftToRight)
        self.label_4.setTextFormat(Qt.PlainText)
        self.label_4.setAlignment(Qt.AlignCenter)

        self.tab2Layout.addWidget(self.label_4)

        self.WaypointsQLineEdit = QLineEdit(self.tab2ButtonsPage)
        self.WaypointsQLineEdit.setObjectName(u"WaypointsQLineEdit")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.WaypointsQLineEdit.sizePolicy().hasHeightForWidth())
        self.WaypointsQLineEdit.setSizePolicy(sizePolicy2)
        self.WaypointsQLineEdit.setLayoutDirection(Qt.LeftToRight)
        self.WaypointsQLineEdit.setStyleSheet(u"QLineEdit {\n"
"    border: none;\n"
"    background: transparent;\n"
"    font-size: 12px;\n"
"	color: white;  \n"
"}")
        self.WaypointsQLineEdit.setAlignment(Qt.AlignCenter)

        self.tab2Layout.addWidget(self.WaypointsQLineEdit)

        self.line_8 = QFrame(self.tab2ButtonsPage)
        self.line_8.setObjectName(u"line_8")
        self.line_8.setFrameShape(QFrame.Shape.HLine)
        self.line_8.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab2Layout.addWidget(self.line_8)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.tab2Layout.addItem(self.horizontalSpacer)

        self.btn_tab2_ExportOverview = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_ExportOverview.setObjectName(u"btn_tab2_ExportOverview")

        self.tab2Layout.addWidget(self.btn_tab2_ExportOverview)

        self.btn_tab2_ExportUnderdeck = QPushButton(self.tab2ButtonsPage)
        self.btn_tab2_ExportUnderdeck.setObjectName(u"btn_tab2_ExportUnderdeck")

        self.tab2Layout.addWidget(self.btn_tab2_ExportUnderdeck)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.tab2Layout.addItem(self.horizontalSpacer_5)

        self.leftPanelStackedWidget.addWidget(self.tab2ButtonsPage)

        self.leftPanelLayout.addWidget(self.leftPanelStackedWidget)


        self.mainHorizontalLayout.addLayout(self.leftPanelLayout)

        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy3.setHorizontalStretch(1)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.tabWidget.sizePolicy().hasHeightForWidth())
        self.tabWidget.setSizePolicy(sizePolicy3)
        self.tabWidget.setMaximumSize(QSize(16777214, 16777215))
        self.tab_0 = QWidget()
        self.tab_0.setObjectName(u"tab_0")
        self.tab0ContentLayout = QVBoxLayout(self.tab_0)
        self.tab0ContentLayout.setObjectName(u"tab0ContentLayout")
        self.tab0_textEdit1_Photo = QTextEdit(self.tab_0)
        self.tab0_textEdit1_Photo.setObjectName(u"tab0_textEdit1_Photo")
        self.tab0_textEdit1_Photo.setStyleSheet(u"QTextEdit {\n"
"  border: none;\n"
"}")

        self.tab0ContentLayout.addWidget(self.tab0_textEdit1_Photo)

        self.line = QFrame(self.tab_0)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.tab0ContentLayout.addWidget(self.line)

        self.graphicsView_crosssection_2 = QGraphicsView(self.tab_0)
        self.graphicsView_crosssection_2.setObjectName(u"graphicsView_crosssection_2")
        self.graphicsView_crosssection_2.setStyleSheet(u"QGraphicsView {\n"
"  border: none;\n"
"}")

        self.tab0ContentLayout.addWidget(self.graphicsView_crosssection_2)

        self.tabWidget.addTab(self.tab_0, "")
        self.tab_1 = QWidget()
        self.tab_1.setObjectName(u"tab_1")
        self.tab1ContentLayout = QVBoxLayout(self.tab_1)
        self.tab1ContentLayout.setObjectName(u"tab1ContentLayout")
        self.tab1_QWebEngineView = QLabel(self.tab_1)
        self.tab1_QWebEngineView.setObjectName(u"tab1_QWebEngineView")
        self.tab1_QWebEngineView.setAlignment(Qt.AlignCenter)

        self.tab1ContentLayout.addWidget(self.tab1_QWebEngineView)

        self.tabWidget.addTab(self.tab_1, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.tab2ContentLayout = QVBoxLayout(self.tab_2)
        self.tab2ContentLayout.setObjectName(u"tab2ContentLayout")
        self.verticalSplitter = QSplitter(self.tab_2)
        self.verticalSplitter.setObjectName(u"verticalSplitter")
        self.verticalSplitter.setOrientation(Qt.Vertical)
        self.verticalSplitter.setHandleWidth(6)
        self.verticalSplitter.setChildrenCollapsible(False)
        self.Placeholder2 = QLabel(self.verticalSplitter)
        self.Placeholder2.setObjectName(u"Placeholder2")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(3)
        sizePolicy4.setHeightForWidth(self.Placeholder2.sizePolicy().hasHeightForWidth())
        self.Placeholder2.setSizePolicy(sizePolicy4)
        self.Placeholder2.setMinimumSize(QSize(0, 200))
        self.Placeholder2.setAlignment(Qt.AlignCenter)
        self.verticalSplitter.addWidget(self.Placeholder2)
        self.dockWidget_FR = QDockWidget(self.verticalSplitter)
        self.dockWidget_FR.setObjectName(u"dockWidget_FR")
        self.dockWidget_FR.setEnabled(True)
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(1)
        sizePolicy5.setHeightForWidth(self.dockWidget_FR.sizePolicy().hasHeightForWidth())
        self.dockWidget_FR.setSizePolicy(sizePolicy5)
        self.dockWidget_FR.setMinimumSize(QSize(272, 322))
        self.dockWidget_FR.setMaximumSize(QSize(524287, 524287))
        self.dockWidget_FR.setAutoFillBackground(False)
        self.dockWidget_FR.setStyleSheet(u"/* Base application background */\n"
"* {\n"
"    background-color: rgba(103, 103, 103, 0.9);  /* Uniform background color for all widgets */\n"
"    color: white;  /* Ensures text is visible against the darker background */\n"
"}\n"
"\n"
"QPushButton {\n"
"    background-color: rgb(139, 139, 139); /* Gray background */\n"
"    color: white;                         /* White text */\n"
"    border-style: solid;\n"
"    border-width: 2px;\n"
"    border-color: #4CAF50;\n"
"    border-radius: 10px;                  /* Rounded corners */\n"
"    padding: 10px;\n"
"    font-size: 16px;\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: #45a049;            /* Darker green background on hover */\n"
"}\n"
"\n"
"QTabWidget::pane { /* The tab widget frame */\n"
"    border-top: 2px solid #C2C7CB;\n"
"    position: absolute;\n"
"    top: -0.5em;\n"
"    color: #333333;\n"
"    background-color: #f0f0f0;\n"
"    border-radius: 5px;\n"
"}\n"
"\n"
"QTabBar::tab {\n"
"    background: #E1E1E1;\n"
"    border: 2px solid #"
                        "C4C4C3;\n"
"    border-bottom-color: #C2C7CB; /* Same as pane color */\n"
"    border-top-left-radius: 4px;\n"
"    border-top-right-radius: 4px;\n"
"    padding: 5px;\n"
"}\n"
"\n"
"QTabBar::tab:selected, QTabBar::tab:hover {\n"
"    background: #fafafa;\n"
"}\n"
"\n"
"QDockWidget {\n"
"    border: 1px solid #d3d3d3; /* Light gray border */\n"
"    border-radius: 5px;        /* Rounded corners */\n"
"    background-color: rgba(255, 255, 255, 0.9); /* White background with slight transparency */\n"
"}\n"
"\n"
"QDockWidget::title {\n"
"    text-align: left;          /* Aligns title text to the left */\n"
"    background-color: rgba(0, 64, 122, 0.85); /* Slightly transparent background for the title */\n"
"    padding: 5px;\n"
"    border-radius: 5px 5px 0 0; /* Rounded corners on the top */\n"
"}\n"
"\n"
"QTextEdit {\n"
"    border: 1px solid #888; /* Slightly lighter border for visibility */\n"
"    border-radius: 5px;  /* Rounded corners */\n"
"    padding: 2px;\n"
"}\n"
"\n"
"QCheckBox {\n"
"    spacing: 5px"
                        "; /* Space between the checkbox and its label */\n"
"}\n"
"\n"
"QCheckBox::indicator {\n"
"    width: 20px;\n"
"    height: 20px;\n"
"    background-color: #888; /* Match background color */\n"
"    border-radius: 5px; /* Rounded corners */\n"
"}\n"
"\n"
"QCheckBox::indicator:checked {\n"
"    background-color: #45a049; /* Green for checked state */\n"
"}\n"
"\n"
"QCheckBox::indicator:unchecked {\n"
"    background-color: #bbb; /* Lighter grey for unchecked state */\n"
"}\n"
"/* Styling for Horizontal Sliders */\n"
"QSlider::groove:horizontal {\n"
"    border: 1px solid #555;  /* Dark grey border for better contrast */\n"
"    height: 10px;            /* Slightly thicker groove for better visibility */\n"
"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #888, stop:1 #bbb); /* Gradient from darker to lighter grey */\n"
"    margin: 2px 0;\n"
"    border-radius: 5px;     /* Soft rounded corners for the groove */\n"
"}\n"
"\n"
"QSlider::handle:horizontal {\n"
"    background: qlineargradient(x1:0, "
                        "y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc); /* Light grey gradient for the handle */\n"
"    border: 1px solid #333; /* Dark border for the handle for better visibility */\n"
"    width: 18px;            /* Width of the handle */\n"
"    margin: -2px 0;         /* Allows handle to overlap the groove slightly */\n"
"    border-radius: 9px;     /* Rounded handle for a smoother look */\n"
"    position: absolute;     /* Ensures the handle is correctly positioned over the groove */\n"
"}\n"
"\n"
"QSlider::handle:horizontal:hover {\n"
"    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff, stop:1 #ddd); /* Brighter gradient for hover effect */\n"
"    border-color: #080;     /* Greenish border on hover for visual feedback */\n"
"}\n"
"\n"
"/* Styling for Vertical Sliders */\n"
"QSlider::groove:vertical {\n"
"    border: 1px solid #555;\n"
"    width: 10px;            /* Consistent width with horizontal */\n"
"    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #888, stop:1 #bbb);\n"
"    m"
                        "argin: 0 2px;\n"
"    border-radius: 5px;\n"
"}\n"
"\n"
"QSlider::handle:vertical {\n"
"    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc);\n"
"    border: 1px solid #333;\n"
"    height: 18px;           /* Height matching the horizontal handle's width */\n"
"    margin: 0 -2px;\n"
"    border-radius: 9px;\n"
"}\n"
"\n"
"QSlider::handle:vertical:hover {\n"
"    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff, stop:1 #ddd);\n"
"    border-color: #080;\n"
"}\n"
"\n"
"\n"
"QDockWidget {\n"
"    border: 1px solid #d3d3d3;\n"
"    border-radius: 10px;\n"
"    background-color: rgb(103, 103, 103);\n"
"}\n"
"\n"
"QDockWidget::title {\n"
"    font-size: 10pt;\n"
"    padding: 8px;\n"
"    background-color: rgba(0, 64, 122, 0.85);\n"
"    border-top-left-radius: 10px;\n"
"    border-top-right-radius: 10px;\n"
"    color: white;\n"
"    font-weight: bold;\n"
"}\n"
"\n"
"QDockWidget > QWidget {\n"
"    border-top-left-radius: 10px;\n"
"    border-top-right-radius: 10px;\n"
""
                        "border: 1px solid #d3d3d3;\n"
"    border-radius: 10px;\n"
"   background-color: rgb(103, 103, 103); /* Maintain transparency to see the dock's styling */\n"
"}\n"
"\n"
"\n"
"\n"
"\n"
"\n"
"\n"
"")
        self.dockWidget_FR.setFloating(False)
        self.dockWidget_FR.setFeatures(QDockWidget.DockWidgetFloatable)
        self.dockWidget_FR.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.dockWidgetContents_FR = QWidget()
        self.dockWidgetContents_FR.setObjectName(u"dockWidgetContents_FR")
        self.dockWidgetContents_FR.setEnabled(True)
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.dockWidgetContents_FR.sizePolicy().hasHeightForWidth())
        self.dockWidgetContents_FR.setSizePolicy(sizePolicy6)
        self.dockWidgetContents_FR.setStyleSheet(u"")
        self.horizontalLayout = QHBoxLayout(self.dockWidgetContents_FR)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.tab3_textEdit = QTextEdit(self.dockWidgetContents_FR)
        self.tab3_textEdit.setObjectName(u"tab3_textEdit")
        sizePolicy6.setHeightForWidth(self.tab3_textEdit.sizePolicy().hasHeightForWidth())
        self.tab3_textEdit.setSizePolicy(sizePolicy6)

        self.horizontalLayout.addWidget(self.tab3_textEdit)

        self.widget_2 = QWidget(self.dockWidgetContents_FR)
        self.widget_2.setObjectName(u"widget_2")
        sizePolicy7 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sizePolicy7.setHorizontalStretch(0)
        sizePolicy7.setVerticalStretch(0)
        sizePolicy7.setHeightForWidth(self.widget_2.sizePolicy().hasHeightForWidth())
        self.widget_2.setSizePolicy(sizePolicy7)
        self.verticalLayout = QVBoxLayout(self.widget_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.labelPF = QLabel(self.widget_2)
        self.labelPF.setObjectName(u"labelPF")
        sizePolicy1.setHeightForWidth(self.labelPF.sizePolicy().hasHeightForWidth())
        self.labelPF.setSizePolicy(sizePolicy1)
        font = QFont()
        font.setBold(True)
        self.labelPF.setFont(font)
        self.labelPF.setLayoutDirection(Qt.LeftToRight)
        self.labelPF.setScaledContents(False)
        self.labelPF.setAlignment(Qt.AlignCenter)
        self.labelPF.setWordWrap(False)

        self.verticalLayout.addWidget(self.labelPF)

        self.comboBox_FlightRoutes_transform = QComboBox(self.widget_2)
        self.comboBox_FlightRoutes_transform.setObjectName(u"comboBox_FlightRoutes_transform")

        self.verticalLayout.addWidget(self.comboBox_FlightRoutes_transform)

        self.label1 = QLabel(self.widget_2)
        self.label1.setObjectName(u"label1")
        sizePolicy8 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sizePolicy8.setHorizontalStretch(0)
        sizePolicy8.setVerticalStretch(0)
        sizePolicy8.setHeightForWidth(self.label1.sizePolicy().hasHeightForWidth())
        self.label1.setSizePolicy(sizePolicy8)
        self.label1.setFont(font)

        self.verticalLayout.addWidget(self.label1)

        self.slider_offset_X = QSlider(self.widget_2)
        self.slider_offset_X.setObjectName(u"slider_offset_X")
        sizePolicy1.setHeightForWidth(self.slider_offset_X.sizePolicy().hasHeightForWidth())
        self.slider_offset_X.setSizePolicy(sizePolicy1)
        self.slider_offset_X.setOrientation(Qt.Horizontal)
        self.slider_offset_X.setTickInterval(0)

        self.verticalLayout.addWidget(self.slider_offset_X)

        self.text_slider_offset_X = QLineEdit(self.widget_2)
        self.text_slider_offset_X.setObjectName(u"text_slider_offset_X")
        sizePolicy2.setHeightForWidth(self.text_slider_offset_X.sizePolicy().hasHeightForWidth())
        self.text_slider_offset_X.setSizePolicy(sizePolicy2)
        self.text_slider_offset_X.setLayoutDirection(Qt.LeftToRight)
        self.text_slider_offset_X.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.text_slider_offset_X)

        self.label2 = QLabel(self.widget_2)
        self.label2.setObjectName(u"label2")
        sizePolicy8.setHeightForWidth(self.label2.sizePolicy().hasHeightForWidth())
        self.label2.setSizePolicy(sizePolicy8)
        self.label2.setFont(font)

        self.verticalLayout.addWidget(self.label2)

        self.slider_offset_Y = QSlider(self.widget_2)
        self.slider_offset_Y.setObjectName(u"slider_offset_Y")
        sizePolicy1.setHeightForWidth(self.slider_offset_Y.sizePolicy().hasHeightForWidth())
        self.slider_offset_Y.setSizePolicy(sizePolicy1)
        self.slider_offset_Y.setOrientation(Qt.Horizontal)
        self.slider_offset_Y.setTickInterval(0)

        self.verticalLayout.addWidget(self.slider_offset_Y)

        self.text_slider_offset_Y = QLineEdit(self.widget_2)
        self.text_slider_offset_Y.setObjectName(u"text_slider_offset_Y")
        sizePolicy2.setHeightForWidth(self.text_slider_offset_Y.sizePolicy().hasHeightForWidth())
        self.text_slider_offset_Y.setSizePolicy(sizePolicy2)
        self.text_slider_offset_Y.setLayoutDirection(Qt.LeftToRight)
        self.text_slider_offset_Y.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.text_slider_offset_Y)

        self.label2_2 = QLabel(self.widget_2)
        self.label2_2.setObjectName(u"label2_2")
        sizePolicy8.setHeightForWidth(self.label2_2.sizePolicy().hasHeightForWidth())
        self.label2_2.setSizePolicy(sizePolicy8)
        self.label2_2.setFont(font)

        self.verticalLayout.addWidget(self.label2_2)

        self.slider_offset_Z = QSlider(self.widget_2)
        self.slider_offset_Z.setObjectName(u"slider_offset_Z")
        sizePolicy1.setHeightForWidth(self.slider_offset_Z.sizePolicy().hasHeightForWidth())
        self.slider_offset_Z.setSizePolicy(sizePolicy1)
        self.slider_offset_Z.setOrientation(Qt.Horizontal)
        self.slider_offset_Z.setTickInterval(0)

        self.verticalLayout.addWidget(self.slider_offset_Z)

        self.text_slider_offset_Z = QLineEdit(self.widget_2)
        self.text_slider_offset_Z.setObjectName(u"text_slider_offset_Z")
        sizePolicy2.setHeightForWidth(self.text_slider_offset_Z.sizePolicy().hasHeightForWidth())
        self.text_slider_offset_Z.setSizePolicy(sizePolicy2)
        self.text_slider_offset_Z.setLayoutDirection(Qt.LeftToRight)
        self.text_slider_offset_Z.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.text_slider_offset_Z)


        self.horizontalLayout.addWidget(self.widget_2)

        self.dockWidget_FR.setWidget(self.dockWidgetContents_FR)
        self.verticalSplitter.addWidget(self.dockWidget_FR)
        self.btnToggleFR = QPushButton(self.verticalSplitter)
        self.btnToggleFR.setObjectName(u"btnToggleFR")
        self.btnToggleFR.setMinimumSize(QSize(9, 30))
        self.btnToggleFR.setStyleSheet(u"\n"
"QPushButton {\n"
"    border-style: solid;\n"
"    border-width: 2px;\n"
"    border-color: #54BCEB;                /* New button border color */\n"
"    border-radius: 10px;                  /* Rounded corners */\n"
"    background-color: transparent;        /* Transparent background */\n"
"    color: white;                         /* White text */\n"
"    padding: 10px;\n"
"    font-size:12px;\n"
"}\n"
"QPushButton:disabled {\n"
"    background-color: #676767;            /* Disabled button color */\n"
"    border-color: #8B8B8B;                /* Disabled button border color */\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: #00407A;            /* Dark blue background on hover */\n"
"}")
        self.verticalSplitter.addWidget(self.btnToggleFR)

        self.tab2ContentLayout.addWidget(self.verticalSplitter)

        self.tabWidget.addTab(self.tab_2, "")

        self.mainHorizontalLayout.addWidget(self.tabWidget)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.leftPanelStackedWidget.setCurrentIndex(0)
        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"ORBIT v.0.98c - Optimized Routing for Bridge Inspection Toolkit  (Research only)", None))
        self.tab0Label.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: white; font-weight: bold; text-align: center;", None))
        self.tab0Label.setText(QCoreApplication.translate("MainWindow", u"Project Setup", None))
        self.label.setText("")
#if QT_CONFIG(tooltip)
        self.btn_tab0_ImportDirectory.setToolTip(QCoreApplication.translate("MainWindow", u"Select input directory containing bridge data files (.xlsx, .kml, .csv, .txt, .png)", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab0_ImportDirectory.setText(QCoreApplication.translate("MainWindow", u"Import Directory", None))
        self.textEdit.setHtml(QCoreApplication.translate("MainWindow", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;\">\n"
"<p align=\"center\" style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:10pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Workflow</span></p>\n"
"<p align=\"center\" style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-size:10pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">1) P"
                        "repare available data:</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">1.1) Select a bridge name, e.g. </span><span style=\" font-size:9pt; color:#00aaff;\">TestBridge</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">1.2) Prepare known trajectory points in 3D (e.g. using MeshLab, if model available) in TestBridge.txt file in the </span><span style=\" font-size:9pt; color:#00aaff;\">Import Directory</span><span style=\" font-size:9"
                        "pt; color:#e7e7e7;\"> in the format:</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">Trajectory:</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100109.101562 195889.515625 13.793574]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100132.921875 195906.546875 14.485563]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100157.093750 195923.562500 14.700541]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-in"
                        "dent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100182.257812 195941.484375 14.491943]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100208.867188 195960.093750 13.645084]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">Pillars:</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100133.992188 195914.203125 6.784123]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100134.429688 195900.734375 6.921566]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margi"
                        "n-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100183.953125 195949.078125 7.142460]</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:8pt; color:#e7e7e7;\">[100184.062500 195936.015625 7.130339]</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">1.3) Prepare a technical drawing of a crosssection and give the inside a blue fill. </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">Mark the longest distance in green t"
                        "o extract the scale = </span><span style=\" font-size:9pt; color:#00aaff;\">input_scale_meters</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">Save it in the </span><span style=\" font-size:9pt; color:#00aaff;\">Import Directory</span><span style=\" font-size:9pt; color:#e7e7e7;\"> as </span><span style=\" font-size:9pt; color:#00aaff;\">TestBridge</span><span style=\" font-size:9pt; color:#e7e7e7;\">_</span><span style=\" font-size:9pt; color:#00aaff;\">crosssection.png</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">2.0) Use </span><span style=\" font-size:9pt; font-weight:600; color:#"
                        "e7e7e7;\">Update Bridge Dat</span><span style=\" font-size:9pt; color:#e7e7e7;\">a and select the import file, if available and select appropriate coordinate system and datum.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">Else, keep project in </span><span style=\" font-size:9pt; color:#00aaff;\">WGS84</span><span style=\" font-size:9pt; color:#e7e7e7;\"> and </span><span style=\" font-size:9pt; color:#00aaff;\">agl</span><span style=\" font-size:9pt; color:#e7e7e7;\"> = Above Ground Level</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">2.1) Use </span><span style=\" font-size:9pt; fon"
                        "t-weight:600; color:#e7e7e7;\">Update Cross section</span><span style=\" font-size:9pt; color:#e7e7e7;\"> to extract the cross section appropriately</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:9pt; color:#e7e7e7;\">2.2) </span><span style=\" font-size:9pt; font-weight:600; color:#e7e7e7;\">Confirm the project</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-size:9pt;\"><br /></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>", None))
#if QT_CONFIG(tooltip)
        self.btn_tab0_LoadBridgeData.setToolTip(QCoreApplication.translate("MainWindow", u"Update project data based on import files, e.g. 3D trajectory data in various formats and crosssection .png", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab0_LoadBridgeData.setText(QCoreApplication.translate("MainWindow", u"Load Bridge Data", None))
#if QT_CONFIG(tooltip)
        self.btn_tab0_updateData.setToolTip(QCoreApplication.translate("MainWindow", u"Update cross-section shape extraction from image with current parameters (scale, epsilon)", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab0_updateData.setText(QCoreApplication.translate("MainWindow", u"Update Crosssection", None))
#if QT_CONFIG(tooltip)
        self.btn_tab0_ConfirmProjectData.setToolTip(QCoreApplication.translate("MainWindow", u"Confirm project data and prepare for 3D modeling", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab0_ConfirmProjectData.setText(QCoreApplication.translate("MainWindow", u"Confirm Project Data", None))
        self.tab1Label.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: white; font-weight: bold; text-align: center;", None))
        self.tab1Label.setText(QCoreApplication.translate("MainWindow", u"Bridge Gemeometry ", None))
        self.label_2.setText("")
        self.trajectoryGroupBox.setTitle(QCoreApplication.translate("MainWindow", u"Trajectory", None))
#if QT_CONFIG(tooltip)
        self.btn_tab1_DrawTrajectory.setToolTip(QCoreApplication.translate("MainWindow", u"Toggle trajectory drawing mode. When active, click on the map to add trajectory points. Click again to exit drawing mode.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab1_DrawTrajectory.setText(QCoreApplication.translate("MainWindow", u"Draw Trajectory", None))
#if QT_CONFIG(tooltip)
        self.btnUndo_trajectory.setToolTip(QCoreApplication.translate("MainWindow", u"Undo last trajectory point.", None))
#endif // QT_CONFIG(tooltip)
        self.btnUndo_trajectory.setText("")
#if QT_CONFIG(tooltip)
        self.btnRedo_trajectory.setToolTip(QCoreApplication.translate("MainWindow", u"Redo last undone trajectory point.", None))
#endif // QT_CONFIG(tooltip)
        self.btnRedo_trajectory.setText("")
        self.pillarsGroupBox.setStyleSheet(QCoreApplication.translate("MainWindow", u"QGroupBox { color: white; font-weight: bold; }", None))
        self.pillarsGroupBox.setTitle(QCoreApplication.translate("MainWindow", u"Pillars", None))
#if QT_CONFIG(tooltip)
        self.btn_tab1_mark_pillars.setToolTip(QCoreApplication.translate("MainWindow", u"Toggle pillar marking mode. When active, click on the map to add pillar pairs.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab1_mark_pillars.setText(QCoreApplication.translate("MainWindow", u"Mark Pillars", None))
#if QT_CONFIG(tooltip)
        self.btnUndo_Pillar.setToolTip(QCoreApplication.translate("MainWindow", u"Undo last pillar.", None))
#endif // QT_CONFIG(tooltip)
        self.btnUndo_Pillar.setText("")
#if QT_CONFIG(tooltip)
        self.btnRedo_Pillar.setToolTip(QCoreApplication.translate("MainWindow", u"Redo last undone pillar.", None))
#endif // QT_CONFIG(tooltip)
        self.btnRedo_Pillar.setText("")
        self.safetyZonesGroupBox.setStyleSheet(QCoreApplication.translate("MainWindow", u"QGroupBox { color: white; font-weight: bold; }", None))
        self.safetyZonesGroupBox.setTitle(QCoreApplication.translate("MainWindow", u"Safety Zones", None))
#if QT_CONFIG(tooltip)
        self.btn_tab1_SafetyZones.setToolTip(QCoreApplication.translate("MainWindow", u"Toggle safety zone drawing mode. When active, click on the map to add corner points (minimum 3 points required).", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab1_SafetyZones.setText(QCoreApplication.translate("MainWindow", u"Safety Zones", None))
#if QT_CONFIG(tooltip)
        self.btnLoad_SafetyZones.setToolTip(QCoreApplication.translate("MainWindow", u"Load safety zones from JSON file. Opens file dialog to select safety zone data.", None))
#endif // QT_CONFIG(tooltip)
        self.btnLoad_SafetyZones.setText("")
#if QT_CONFIG(tooltip)
        self.btnUndo_Safety.setToolTip(QCoreApplication.translate("MainWindow", u"Undo last safety zone action.", None))
#endif // QT_CONFIG(tooltip)
        self.btnUndo_Safety.setText("")
#if QT_CONFIG(tooltip)
        self.btnRedo_Safety.setToolTip(QCoreApplication.translate("MainWindow", u"Redo last undone safety zone action.", None))
#endif // QT_CONFIG(tooltip)
        self.btnRedo_Safety.setText("")
#if QT_CONFIG(tooltip)
        self.btnAdd_Safety.setToolTip(QCoreApplication.translate("MainWindow", u"Completes current zone and start a new safety zone.", None))
#endif // QT_CONFIG(tooltip)
        self.btnAdd_Safety.setText("")
#if QT_CONFIG(tooltip)
        self.btn_tab1_build_model.setToolTip(QCoreApplication.translate("MainWindow", u"Construct a 3D representation based on cross section and 3D trajectory data (taking trajectory_heights into account for AboveGroundLevel projects)", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab1_build_model.setText(QCoreApplication.translate("MainWindow", u"Build Model", None))
        self.tab2Label.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: white; font-weight: bold; text-align: center;", None))
        self.tab2Label.setText(QCoreApplication.translate("MainWindow", u"Flightroute Generation", None))
        self.label_3.setText("")
#if QT_CONFIG(tooltip)
        self.btn_tab2_TopView.setToolTip(QCoreApplication.translate("MainWindow", u"Switch to top view", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_TopView.setText(QCoreApplication.translate("MainWindow", u"Top View", None))
#if QT_CONFIG(tooltip)
        self.btn_tab2_UpdateSafetyZones.setToolTip(QCoreApplication.translate("MainWindow", u"Update safety zones in 3D viewer based on map data", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_UpdateSafetyZones.setText(QCoreApplication.translate("MainWindow", u"Update Safety Zones", None))
#if QT_CONFIG(tooltip)
        self.btn_tab2_LoadPC.setToolTip(QCoreApplication.translate("MainWindow", u"Load point cloud file (.ply, .pcd, .xyz, .las) with coordinate system selection and automatic tranformation to project CS.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_LoadPC.setText(QCoreApplication.translate("MainWindow", u"Load Point Cloud", None))
#if QT_CONFIG(tooltip)
        self.btn_tab2_Dock_updateOverviewFlight.setToolTip(QCoreApplication.translate("MainWindow", u"Generate overview flight routes using current parameters", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_Dock_updateOverviewFlight.setText(QCoreApplication.translate("MainWindow", u"Update Overview Flight ", None))
#if QT_CONFIG(tooltip)
        self.btn_tab2_Dock_updateInspectionRoute.setToolTip(QCoreApplication.translate("MainWindow", u"Generate under-deck inspection routes", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_Dock_updateInspectionRoute.setText(QCoreApplication.translate("MainWindow", u"Update Inspection  Route", None))
#if QT_CONFIG(tooltip)
        self.WaypointsSlider.setToolTip("")
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.label_4.setToolTip(QCoreApplication.translate("MainWindow", u"Simplify flight route by removing waypoints that don't change direction significantly. Use lower threshold to follow curvatures.", None))
#endif // QT_CONFIG(tooltip)
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Simplify by angle threshold", None))
#if QT_CONFIG(tooltip)
        self.WaypointsQLineEdit.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.WaypointsQLineEdit.setText(QCoreApplication.translate("MainWindow", u"0", None))
#if QT_CONFIG(tooltip)
        self.btn_tab2_ExportOverview.setToolTip(QCoreApplication.translate("MainWindow", u"Export overview flight routes as KML files zipped as DJI-compatible KMZ files", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_ExportOverview.setText(QCoreApplication.translate("MainWindow", u"Export Overview", None))
#if QT_CONFIG(tooltip)
        self.btn_tab2_ExportUnderdeck.setToolTip(QCoreApplication.translate("MainWindow", u"Export underdeck inspection routes as KML files zipped as DJI-compatible KMZ files", None))
#endif // QT_CONFIG(tooltip)
        self.btn_tab2_ExportUnderdeck.setText(QCoreApplication.translate("MainWindow", u"Export Inspection", None))
        self.tab0_textEdit1_Photo.setHtml(QCoreApplication.translate("MainWindow", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;\">\n"
"<p align=\"center\" style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Project Information</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">bridge_name = </span><span style=\" font-size:11pt; color:#00aaff;\">TestBridge </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#6a9955;\"># Input data should have {</span><span style=\" font-size:11p"
                        "t; color:#e7e7e7;\">bridge_name</span><span style=\" font-size:11pt; color:#6a9955;\">}</span><span style=\" font-size:11pt; color:#e7e7e7;\"> </span><span style=\" font-size:11pt; color:#6a9955;\">and be in</span><span style=\" font-size:11pt; color:#e7e7e7;\"> import_dir</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">import_dir = </span><span style=\" font-size:11pt; color:#00aaff;\">C:\\Code\\Orbitv0.98c\\01_ImportFolder</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">project_dir_base = </span><span style=\" font-size:11pt; color:#00aaff;\">C:\\Code\\Orbitv0.98c\\02_FlightRoutes </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#6a9955;\"># base for the project output</span></p>\n"
"<p style=\" m"
                        "argin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Trajectory </span><span style=\" font-size:11pt; text-decoration: underline; color:#e7e7e7;\">(If no import data available)</span><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">: </span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">trajectory_heights = </span><span style=\" font-size:11pt; color:#00aaff;\">[5, 5, 5, 5, 5] </span><span style=\" font-size:11pt; color:#6a9955;\"># Approx. height of bridge trajectory above starting point, quadratic approx. </span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Aptos,sans-serif';"
                        " font-size:11pt; color:#e7e7e7;\">ground_elevation</span><span style=\" font-size:11pt; color:#e7e7e7;\"> = </span><span style=\" font-size:11pt; color:#00aaff;\">0 </span><span style=\" font-size:11pt; color:#6a9955;\"># Purely cosmetic. Defines pillar base altitude. </span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Cross-section:</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">input_scale_meters = </span><span style=\" font-size:11pt; color:#00aaff;\">14.05 </span><span style=\" font-size:11pt; color:#6a9955;\"># Mark one distance in "
                        "green. bridge_width is the largest distance across.</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">epsilonInput =</span><span style=\" font-size:11pt; color:#00aaff;\"> 0.003 </span><span style=\" font-size:11pt; color:#6a9955;\"># Smaller value is tighter fit</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Coordinate system:</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#e7e7e7;\">coordinate_system = </span"
                        "><span style=\" font-size:11pt; color:#00aaff;\">WGS84 , </span><span style=\" font-size:11pt; color:#6a9955;\"># </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#6a9955;\">Lambert72, or any EPSG code </span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Imported data:</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Segoe UI'; font-size:11pt; color:#e7e7e7;\">trajectory_points_count = 0</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px"
                        ";\"><span style=\" font-family:'Segoe UI'; font-size:11pt; color:#e7e7e7;\">pillars_count = 0</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Segoe UI'; font-size:11pt; color:#e7e7e7;\">trajectory_length = 0</span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Segoe UI'; font-size:11pt; color:#e7e7e7;\">average_pillar_height = 0</span></p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_0), QCoreApplication.translate("MainWindow", u"1) Project Information", None))
        self.tab1_QWebEngineView.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: white; font-size: 14px; background-color: rgba(0,0,0,0.3); padding: 20px;", None))
        self.tab1_QWebEngineView.setText(QCoreApplication.translate("MainWindow", u"Map Widget Area\n"
"(QWebEngineView would be inserted here via layout)", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_1), QCoreApplication.translate("MainWindow", u"2) Statellite map ", None))
        self.Placeholder2.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: white; font-size: 14px; background-color: rgba(0,0,0,0.3); padding: 20px;", None))
        self.Placeholder2.setText(QCoreApplication.translate("MainWindow", u"3D Visualization Area\n"
"(This would contain your visualization widget)", None))
        self.dockWidget_FR.setWindowTitle(QCoreApplication.translate("MainWindow", u"Flight Route Settings", None))
        self.tab3_textEdit.setHtml(QCoreApplication.translate("MainWindow", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Overview Flight: </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">order</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><sp"
                        "an style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> [</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;101&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">, </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;r102&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">,</span><span style=\" font-size:11pt; color:#9cdcfe;\">transition_mode</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">,</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;201&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">, </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&q"
                        "uot;r202&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">] </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># 1=right side, r=reverse. useing offsets as in </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">standard_flight_routes (</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">below)</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#9cdcfe;\">transition_mode</span><span style=\" font-size:11pt; color:#e7e7e7;\"> = </span><span style=\" font-size:11pt; color:#ce9178;\">2</span><span style=\" font-size:11pt; color:#e7e7e7;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># 0 = separate right and left side, 1=pass middle, 2=aft"
                        "er last segment</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">transition_vertical_offset = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">15 </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Or underneath e.g. -6 </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">transition_horizontal_offset = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">15</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0"
                        "px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Safety Zones:</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">safety_zones_clearance</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[[0,20],[15,30],[10,20]]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cc"
                        "cccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">#min, max local. default 0,35 m</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"><br /></span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">safety_zones_clearance_adjust</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[[21],[14],[20],[20]]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0;"
                        " text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># adjust points inside zones. 0 = delete points, -1 find closest exit</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Underdeck Flights: </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">num_points</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color"
                        ":#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[3, 7, 3]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Base points per section </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">horizontal_offsets_underdeck</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span"
                        "><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[13, 13, 13]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># H_Offest of base points </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">height_offsets_underdeck</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[[5, 5, 5], [5, 5, 5], [5, 5, 5]]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ccccc"
                        "c;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Vertical offset below trajectory (consider slab) using quadratic approx per base point.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">general_height_offset</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\"> 1</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">thresholds_zones</span><span style=\" f"
                        "ont-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[(10, 10), (10, 10), (10, 10)]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Threshold distance </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">custom_zone_angles = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[]</span><span style=\" font-famil"
                        "y:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\"># </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">[2.16, 2.20, 2.24]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:8pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Adjust angle</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">connection_height </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\"> 20</span><span style=\" font-family:'Consolas,Courier New,monosp"
                        "ace'; font-size:11pt; color:#b5cea8;\">	</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># vertical flight height for connections</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">num_passes</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">2		</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># num passes underdeck flighs</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top"
                        ":0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#6a9955;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Export Modus:</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">heightMode = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">EGM96 </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">#</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">relativeToStartPoint</span><span style=\" font-family"
                        ":'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"> or EGM96</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">heightStartingPoint_Ellipsoid = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">0 </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Typically </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">50.2 m </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">in Belgium.</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">Place drone on ground and read EXIF from image"
                        " / RTK settings</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">heightStartingPoint_Reference = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">0 </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Typically </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">8.0 m</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">.</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\">Height in geolocated point cloud </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-"
                        "right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># Z waypoint= bridge trajectory (e.g. </span><span style=\" font-size:11pt; color:#e7e7e7;\">trajectory_heights)</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"> + offsets + </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">heightStartingPoint_Ellipsoid - heightStartingPoint_Reference</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; font-weight:600; text-decoration: underline; color:#e7e7e7;\">Additional Features:</spa"
                        "n></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">safety_check_photo </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">= </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">1</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">safety_check_underdeck </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">= </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[[0],[0],[0]]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\"> </"
                        "span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># 1 = execute safety check. </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">safety_check_underdeck_axial </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">= </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">[[0],[0],[0]]</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># 1 = execute safety check.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#9cdcfe;\">n_gird"
                        "ers</span><span style=\" font-size:11pt; color:#e7e7e7;\"> = </span><span style=\" font-size:11pt; color:#ce9178;\">3</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#9cdcfe;\">underdeck_split</span><span style=\" font-size:11pt; color:#e7e7e7;\"> = </span><span style=\" font-size:11pt; color:#ce9178;\">1</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:11pt; color:#9cdcfe;\">underdeck_axial</span><span style=\" font-size:11pt; color:#e7e7e7;\"> = </span><span style=\" font-size:11pt; color:#ce9178;\">0</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">droneEnumValue = </span><span style=\" font-famil"
                        "y:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">77 </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># M3E = 77 </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">payloadEnumValue = </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">66 </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># M3E = 66 </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Segoe WPC,Segoe UI,sans-serif'; font-size:11pt; color:#9cdcfe;\">globalWaypointTurnMode</span><span style=\" font-family:'Segoe WPC,Segoe UI,sans-serif'; font-size:11pt; color:#d8dee9;\"> </span><span style=\" "
                        "font-family:'Segoe WPC,Segoe UI,sans-serif'; font-size:11pt; color:#9cdcfe;\">=</span><span style=\" font-family:'Segoe WPC,Segoe UI,sans-serif'; font-size:11pt; color:#d8dee9;\"> </span><span style=\" font-family:'Segoe WPC,Segoe UI,sans-serif'; font-size:11pt; color:#ce9178;\">toPointAndStopWithDiscontinuityCurvature </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"># coordinateTurn, toPointAndStopWithContinuityCurvature, toPointAndPassWithContinuityCurvature</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#4eea00;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">standard_flight_routes</span><span style"
                        "=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> {</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;101&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;vertical_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: 8, </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;distance_offset&quot;</span><span style=\" fo"
                        "nt-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#b5cea8;\">5</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;102&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;vertical_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#b5cea8;\">3</span><span style=\" font-family:'Consolas,Courier New,mo"
                        "nospace'; font-size:11pt; color:#cccccc;\">, </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;distance_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#b5cea8;\">2</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;201&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;vertical_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'"
                        "; font-size:11pt; color:#cccccc;\">: 8, </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;distance_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: 5},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;202&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;vertical_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#b5cea8;\">3</span><span style=\" font-family:'Consolas,Courier New,monospace'; "
                        "font-size:11pt; color:#cccccc;\">, </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;distance_offset&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#b5cea8;\">2</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">}}</span></p>\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"><br /></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">flight_speed_map</span><span style=\" font-family:'Consolas,Courier New,monospace'; f"
                        "ont-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> {</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;101&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;6&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">}"
                        ",</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;102&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;4&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\"> </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;201&quot;</span><span style"
                        "=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;6&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;202&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,mono"
                        "space'; font-size:11pt; color:#ce9178;\">&quot;4&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;103&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;3&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11"
                        "pt; color:#ce9178;\">&quot;203&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;3&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;104&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178"
                        ";\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;3&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;105&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;2&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\""
                        " margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;204&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;3&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;205&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,"
                        "Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;2&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;transition&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier N"
                        "ew,monospace'; font-size:11pt; color:#ce9178;\">&quot;2.5&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},<br /></span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;underdeck_span1&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;0.8&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier"
                        " New,monospace'; font-size:11pt; color:#ce9178;\">&quot;underdeck_span2&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;0.85&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;underdeck_span3&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consol"
                        "as,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;0.8&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;connection&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Cour"
                        "ier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;2.5&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},	 </span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;axial_span1&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;1.0&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bot"
                        "tom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;axial_span2&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;1.0&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">},</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;axial_span3&quot;</span><span style=\" font-"
                        "family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: {</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;speed&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">: </span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#ce9178;\">&quot;1.0&quot;</span><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">}</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#cccccc;\">}}</span></p></body></html>", None))
        self.labelPF.setText(QCoreApplication.translate("MainWindow", u"Transformation", None))
        self.label1.setText(QCoreApplication.translate("MainWindow", u"X offset:", None))
#if QT_CONFIG(tooltip)
        self.slider_offset_X.setToolTip("")
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.text_slider_offset_X.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.text_slider_offset_X.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.label2.setText(QCoreApplication.translate("MainWindow", u"Y offset:", None))
#if QT_CONFIG(tooltip)
        self.slider_offset_Y.setToolTip("")
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.text_slider_offset_Y.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.text_slider_offset_Y.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.label2_2.setText(QCoreApplication.translate("MainWindow", u"Z offset:", None))
#if QT_CONFIG(tooltip)
        self.slider_offset_Z.setToolTip("")
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.text_slider_offset_Z.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.text_slider_offset_Z.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.btnToggleFR.setText("")
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("MainWindow", u"3) Flightroute Generation", None))
    # retranslateUi

