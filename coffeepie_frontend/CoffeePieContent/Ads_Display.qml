import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 1920
    height: 1080

    property string adImageUrl: ""
    property string adTitle: ""
    property string adBody: ""
    property string adLink: ""
    property string campaignId: ""
    property int creditsRewarded: 0
    property int countdown: 5

    Rectangle {
        id: mainMenu
        x: 0
        y: 0
        width: 1920
        height: 1080
        color: "#000000"

        Button {
            id: buttonClose
            x: 1812
            y: 10
            width: 100
            height: 92
            icon.width: 80
            icon.source: "images/Close_Button.png"
            icon.height: 80
            icon.color: "#ffffff"
            flat: true
            onClicked: stackView.clear()
        }

        Text {
            id: lblAdTitle
            x: 0
            y: 40
            width: 1920
            height: 50
            color: "#ffffff"
            text: adTitle || tr.tr("Anuncio Patrocinado")
            font.pixelSize: 32
            horizontalAlignment: Text.AlignHCenter
        }

        Rectangle {
            id: adContainer
            x: 260
            y: 120
            width: 1400
            height: 600
            color: "#222222"
            radius: 8
            border.color: "#444444"

            Image {
                id: adImage
                anchors.fill: parent
                anchors.margins: 20
                source: adImageUrl
                fillMode: Image.PreserveAspectFit
                visible: adImageUrl !== ""
            }

            Text {
                id: lblAdBody
                x: 20
                y: 20
                width: 1360
                color: "#cccccc"
                text: adBody
                font.pixelSize: 20
                wrapMode: Text.WordWrap
                visible: adBody !== ""
            }
        }

        Text {
            id: lblReward
            x: 0
            y: 750
            width: 1920
            height: 40
            color: "#c18b44"
            text: tr.tr("Recibirás") + " " + creditsRewarded + " " + tr.tr("créditos por ver este anuncio")
            font.pixelSize: 24
            horizontalAlignment: Text.AlignHCenter
            visible: creditsRewarded > 0
        }

        Text {
            id: lblTimer
            x: 0
            y: 800
            width: 1920
            height: 40
            color: "#888888"
            text: tr.tr("Puedes cerrar en") + " " + countdown + "s"
            font.pixelSize: 20
            horizontalAlignment: Text.AlignHCenter
        }

        Button {
            id: btnClaim
            x: 760
            y: 870
            width: 400
            height: 60
            text: tr.tr("Reclamar créditos")
            font.pointSize: 18
            enabled: countdown <= 0
            onClicked: {
                api.claimAdReward()
                stackView.clear()
            }
        }

        Button {
            id: btnSkip
            x: 820
            y: 940
            width: 280
            height: 40
            text: tr.tr("Omitir")
            font.pointSize: 14
            flat: true
            palette.buttonText: "#888888"
            onClicked: stackView.clear()
        }
    }

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        running: true
        onTriggered: {
            if (countdown > 0) {
                countdown--
            } else {
                countdownTimer.stop()
            }
        }
    }

    Connections {
        target: api
        function onAdReady(data) {
            var ad = JSON.parse(data)
            adTitle = ad.campaign_name || ""
            creditsRewarded = ad.bid_amount || 0
            campaignId = ad.campaign_id || ""
            var content = ad.ad_content || {}
            adImageUrl = content.image_url || content.media_url || ""
            adBody = content.body || content.description || ""
            adLink = content.url || content.link || ad.ad_url || ""
        }
        function onAdRewarded(data) {
            var r = JSON.parse(data)
            creditsRewarded = r.credits_rewarded || 0
        }
    }
}
