# -*- coding: utf-8 -*-
# Related to no_selection
# Test code for no selecion option

# This files is part of anki-web-browser addon
# @author ricardo saturnino
# ------------------------------------------------

import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/../')
sys.argv.append('-awb-test')

import src.config.main as cc
import src.no_selection as ns
from aqt.qt import *

app = QApplication(sys.argv)

_tested = ns.NoSelectionViewAdapter

# TODO: test no selection...

@pytest.fixture()
def setup():
    pass

def bltest_loadOK():
    pass
    # cc.currentLocation = os.path.dirname(os.path.realpath(__file__))
    # os.remove(cc.currentLocation + '/' + cc.CONFIG_FILE)
    # config = _tested.load()
    # assert config is not None
    # assert (config.keepBrowserOpened is True)


if __name__ == '__main__':
    # if '-view' in sys.argv:
    main = QMainWindow()
    view = ns.NoSelectionController(main)
    view.setFields({
        1: "State",
        2: "City",
        3: "Stadion"
    })
    # view.open()
    view.open()
    sys.exit(app.exec())
