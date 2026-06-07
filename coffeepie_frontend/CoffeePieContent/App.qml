// Copyright (C) 2021 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR GPL-3.0-only

import QtQuick
import CoffeePie
import QtQuick.Controls


Window {
    visible: true
    title: "CoffeePie"

    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint

    Login_Screen {
        id: mainScreen
    }

}

