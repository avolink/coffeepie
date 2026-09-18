import QtQuick  2.15
import QtQuick.Controls  2.15
import QtQuick.Window  2.15
import QtQuick.Dialogs 1.2


Window {
    visible: true
    width: 1920
    height: 1080
    visibility: "FullScreen"

    Item {
        id: root
        width: 1920
        height: 1080

        property string userToken: ""

        StackView {
            id: stackView
            x: 0
            y: 0
            width: 1920
            height: 1080

            Image {
                id: coffee_Background
                width: 1920
                height: 1080
                source: "images/Coffee_Background.jpg"
                sourceSize.height: 1080
                sourceSize.width: 1902
                fillMode: Image.Stretch
                RoundButton {
                    id: loginButton
                    x: 941
                    y: 851
                    width: 103
                    height: 103
                    text: "+"
                    icon.width: 120
                    icon.source: "images/Login_Button.png"
                    icon.height: 120
                    icon.color: "#007a2828"
                    flat: true
                    Connections {
                        target: loginButton
                        function onClicked() {
                            var email = inputFieldUser.text;
                            var password = inputFieldPassword.text;
                            if (!email || !password) {
                                userCreatedDialog.text = "Por favor ingrese usuario y contraseña.";
                                userCreatedDialog.visible = true;
                                return;
                            }
                            var result = myMachine.loginUser(email, password, "");
                            if (result && result.access_token) {
                                myMachine.userToken = result.access_token; // Store the token globally
                                stackView.push("Home_Screen.qml");
                            } else if (result && result.detail) {
                                userCreatedDialog.text = result.detail;
                                userCreatedDialog.visible = true;
                            } else {
                                userCreatedDialog.text = "Error de autenticación.";
                                userCreatedDialog.visible = true;
                            }
                        }
                    }
                }

                Text {
                    id: labelCoffeePie
                    x: 732
                    y: 195
                    width: 500
                    height: 73
                    color: "#eaeaea"
                    text: qsTr("Coffee Pie®")
                    font.pixelSize: 60
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    id: labelLogin
                    x: 732
                    y: 355
                    width: 500
                    height: 73
                    color: "#eaeaea"
                    text: qsTr("Inicio de Sesión")
                    font.pixelSize: 60
                    horizontalAlignment: Text.AlignHCenter
                }

                Button {
                    id: buttonHelp
                    x: 33
                    y: 33
                    width: 120
                    height: 80
                    icon.width: 100
                    icon.source: "images/Support_Button.png"
                    icon.height: 100
                    icon.color: "#eaeaea"
                    flat: true
                }

                Connections {
                    target: buttonHelp
                    function onClicked() { aboutMenu.visible = true }
                }

                Button {
                    id: buttonnewAccount
                    x: 745
                    y: 647
                    width: 474
                    height: 46
                    flat: true

                    Text {
                        id: linkNewAccount
                        x: 0
                        y: 6
                        width: 474
                        height: 37
                        color: "#eaeaea"
                        text: qsTr("Crear cuenta nueva")
                        font.pixelSize: 26
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignTop
                    }
                }

                Connections {
                    target: buttonnewAccount
                    function onClicked() {
                        createUserDialog.open()
                    }
                }

                Dialog {
                    id: createUserDialog
                    width: 420
                    height: 650
                    visible: false
                    title: qsTr("Crear cuenta nueva")
                    standardButtons: Dialog.Ok | Dialog.Cancel
                    onAccepted: formCreateUserComponent.submitUser()
                    onRejected: visible = false

                    FormCreateUser {
                        id: formCreateUserComponent
                        anchors.fill: parent
                        function submitUser() {
                            var userData = {
                                name: name,
                                email: email,
                                type: type,
                                companyID: companyID,
                                age: parseInt(age),
                                city: city,
                                occupation: occupation,
                                portions: parseInt(portions),
                                password: password
                            }
                            myMachine.createUser(userData)
                            createUserDialog.visible = false
                        }
                    }
                }

                Button {
                    id: buttonForgotPassword
                    x: 745
                    y: 809
                    width: 474
                    height: 36
                    text: qsTr("")
                    flat: true

                    Text {
                        id: linkRecoverPassword
                        x: 0
                        y: 3
                        width: 474
                        height: 30
                        color: "#eaeaea"
                        text: qsTr("Restablecer contraseña")
                        font.pixelSize: 24
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            Image {
                id: input_Field_Vector1
                x: 743
                y: 554
                width: 479
                height: 101
                source: "images/Input_Field_Vector.png"
                fillMode: Image.PreserveAspectFit

                TextField {
                    id: inputFieldUser
                    x: 10
                    y: 11
                    width: 458
                    height: 78
                    visible: true
                    selectedTextColor: "#ffffff"
                    selectionColor: "#908f8f"
                    inputMask: ""
                    font.pointSize: 20
                    placeholderText: qsTr("Usuario")
                    background: Rectangle { color: "transparent" }
                    onFocusChanged: if (focus) selectAll()
                    Keys.onReturnPressed: {
                        nextItemInFocusChain().forceActiveFocus()
                    }
                }
            }

            Image {
                id: input_Field_Vector2
                x: 743
                y: 717
                width: 479
                height: 95
                source: "images/Input_Field_Vector.png"
                fillMode: Image.PreserveAspectFit
            }

            Image {
                id: coffee_Pie_Logo
                x: 865
                y: 55
                source: "../CoffeePieContent/images/Coffee_Pie_Logo.png"
                fillMode: Image.PreserveAspectFit
            }

            TextField {
                id: inputFieldPassword
                x: 750
                y: 725
                width: 458
                height: 78
                visible: true
                echoMode: TextInput.Password
                selectionColor: "#908f8f"
                selectedTextColor: "#ffffff"
                placeholderText: qsTr("Contraseña")
                inputMask: ""
                font.pointSize: 20
                onFocusChanged: if (focus) selectAll()
                background: Rectangle { color: "transparent" }
                Keys.onReturnPressed: {
                    stackView.push("Home_Screen.qml")
                }
            }
        }
    }

    Rectangle {
        id: aboutMenu
        x: 235
        y: 110
        width: 1450
        height: 860
        visible: false
        color: "#323030"

        MouseArea {
            id: mouseAreaExit
            x: -237
            y: -112
            width: 1922
            height: 1084

            Connections {
                target: mouseAreaExit
                function onClicked() { aboutMenu.visible = false }
            }

            MouseArea {
                id: mouseNeutralArea
                x: 237
                y: 112
                width: 1450
                height: 860
                Connections {
                    target: mouseNeutralArea
                    function onClicked() { console.log("clicked") }
                }

                Button {
                    id: buttonClose
                    x: 1346
                    y: 8
                    width: 100
                    height: 92
                    icon.width: 80
                    icon.source: "images/Close_Button.png"
                    icon.height: 80
                    icon.color: "#f2f8f9"
                    flat: true
                    Connections {
                        target: buttonClose
                        function onClicked() { aboutMenu.visible = false }
                    }
                }

                Text {
                    id: lblTechSupport
                    x: 601
                    y: 776
                    width: 250
                    height: 56
                    color: "#f2f8f9"
                    text: qsTr("Soporte Técnico")
                    font.pixelSize: 30
                    horizontalAlignment: Text.AlignHCenter
                    font.bold: false
                }

                RoundButton {
                    id: roundButtonTechSupport
                    x: 668
                    y: 656
                    width: 114
                    height: 114
                    text: "+"
                    icon.width: 200
                    icon.source: "images/Tech_Support.png"
                    icon.height: 200
                    icon.color: "#00000000"
                    Connections {
                        target: roundButtonTechSupport
                        function onClicked() { console.log("clicked") }
                    }
                }

                Rectangle {
                    id: boxPrivacyPolicy
                    x: 282
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"

                    ScrollView {
                        id: scrollView
                        x: 0
                        y: 0
                        width: 1064
                        height: 546

                        Text {
                            id: txtPrivacyPolicy
                            x: 16
                            y: 17
                            width: 1032
                            height: 511
                            color: "#f2f8f9"
                            text: qsTr("PROTECCIÓN DE DATOS\n\n \n\nDe conformidad con lo establecido en Ley 1581 de 2012 y sus decretos reglamentarios de Protección de Datos de Carácter Personal, por el que se regula el derecho de información en la recolección de datos le informamos lo siguiente: - Los datos de carácter personal que nos ha suministrado en ésta y otras comunicaciones mantenidas con usted (Cliente) serán objeto de tratamiento en los ficheros responsabilidad de PANELESA S.A.S. - La finalidad del tratamiento es la de gestionar de forma adecuada la prestación del servicio que nos ha requerido. Asimismo, estos datos no serán cedidos a terceros, salvo las cesiones legalmente permitidas. - Los datos solicitados a través de esta y otras comunicaciones son de suministro obligatorio para la prestación del servicio. Estos son adecuados, pertinentes y no excesivos. - Su negativa a suministrar los datos solicitados implica la imposibilidad de prestarle el servicio. - Igualmente, le informamos de la posibilidad de ejercitar los correspondientes derechos de acceso, rectificación, cancelación y oposición de conformidad con lo establecido en la Ley 1581 de 2012 ante PANELESA S.A.S. como responsables del manejo de los datos aquí suministrados. Los derechos mencionados los puede ejercitar a través del correo electrónico: atencionalcliente@panelesa.com\n\n \n\n​\n\nPOLÍTICA MANEJO DE INFORMACIÓN Y DATOS PERSONALES DE PANELESA S.A.S. Versión: 1\n\nFecha entrada en Vigencia: abril de 2019.\n\nÚltima Actualización: Febrero de 2019.\n\n \n\nGENERALIDADES La presente política se define de conformidad con la entrada en vigencia de la Ley Estatutaria 1581 de 2012 la cual tiene por objeto dictar las disposiciones generales para la protección de datos personales y desarrollar el derecho constitucional que tienen todas las personas a conocer, actualizar y rectificar las informaciones que se hayan recogido sobre ellas en bases de datos o archivos así como el derecho a la información; por tanto, PANELESA S.A.S. teniendo en cuenta su condición de responsable del tratamiento de datos de carácter personal que le asiste, se permite formular el presente texto en aras de dar efectivo cumplimiento a dicha normatividad y en especial para la atención de consultas y reclamos acerca del tratamiento de los datos de carácter personal que recoja y maneje PANELESA S.A.S. El derecho al HÁBEAS DATA es aquel que tiene toda persona de conocer, actualizar y rectificar la información que se haya recogido sobre ella en archivos y bancos de datos de naturaleza pública o privada y le garantiza a todos los ciudadanos poder de decisión y control sobre su información personal. Por tanto, PANELESA S.A.S. acoge tales disposiciones teniendo en cuenta que, para el desarrollo de su objeto social, continuamente está recopilando y efectuando diversos tratamientos a bases de datos tanto de clientes, accionistas, proveedores, aliados comerciales y empleados. En virtud de lo anterior, dentro del deber legal y corporativo de PANELESA S.A.S. de proteger el derecho a la privacidad de las personas, así como la facultad de conocer, actualizar o solicitar la información que sobre ellas se archive en bases de datos, PANELESA S.A.S. ha diseñado la presente política de manejo de la información de carácter personal y bases de datos en la cual se describe y explica el tratamiento de la Información Personal a la que tiene acceso a través de nuestro sitio web , correo electrónico, información física (facturas), mensajes de texto, mensaje de voz, llamadas telefónicas, cara a cara, medios físicos o electrónicos, actuales o que en el futuro se desarrollen como otras comunicaciones enviadas así como por intermedio de terceros que participan en nuestra relación comercial o legal con todos nuestros clientes, empleados, proveedores, accionistas, aliados estratégicos y vinculados. La presente se irá ajustando en la medida en que se vaya reglamentando la normatividad aplicable a la materia y entren en vigencia nuevas disposiciones. OBJETIVO GENERAL Con la implementación de ésta política, se pretende garantizar la reserva de la información y la seguridad sobre el tratamiento que se le dará a la misma a todos los clientes, proveedores, empleados y terceros de quienes PANELESA S.A.S. ha obtenido legalmente información y datos personales conforme a los lineamientos establecidos por la ley regulatoria del derecho al Habeas Data. Asimismo, a través de la expedición de la presente política se da cumplimiento a lo previsto en el literal K del artículo 17 de la referida ley. DEFINICIONES 1. Autorización: Consentimiento que, de manera previa, expresa e informada emite el titular de algún dato personal para que la compañía lleve a cabo el tratamiento de sus datos personales. 2. Titular: persona natural cuyos datos son objeto de tratamiento por parte de la compañía. 3. Base de datos: Conjunto de datos personales. 4. Dato personal: Información que está vinculada a una persona. Es cualquier pieza de información vinculada a una o varias personas determinadas o determinables o que puedan asociarse con una persona natural o jurídica. Los datos personales pueden ser públicos, semiprivados o privados. 5. Tratamiento: Cualquier operación o conjunto de operaciones sobre datos personales dentro de las cuales se puede incluir su recolección, almacenamiento, uso, circulación o supresión. 6. Encargado del tratamiento: Persona natural o jurídica, pública o privada, que por sí misma o en asocio con otros, realiza algún tratamiento sobre datos personales por cuenta del responsable del tratamiento. 7. Responsable del tratamiento: Persona natural o jurídica, pública o privada, que por sí misma o en asocio con otros, decida sobre la base de datos y/o el tratamiento de los datos. 8. Dato público: Es aquel dato calificado como tal según los mandatos de la ley o de la Constitución Política. Son públicos, entre otros, los datos contenidos en documentos públicos, sentencias judiciales ejecutoriadas que no estén sometidas a reserva y los relativos al estado civil de las personas. 9. Dato semiprivado: Es semiprivado el dato que no tiene naturaleza íntima, reservada, ni pública y cuyo conocimiento o divulgación puede interesar no sólo a su titular sino a cierto sector o grupo de personas o a la sociedad en general, como el dato financiero y crediticio de actividad comercial. 10. Dato privado: Es el dato que por su naturaleza íntima o reservada sólo es relevante para el titular. 11. Dato sensible: aquellos relacionados con el origen racial o étnico, la pertenencia a sindicatos, organizaciones sociales o de derechos humanos, convicciones políticas, religiosas, de la vida sexual, biométricos o datos de la salud. Esta información podrá no ser otorgada por el Titular de estos datos. 12. Aviso de privacidad: Documento físico, electrónico generado por el Responsable del tratamiento que es puesto a disposición del titular con la información relativa a la existencia de las políticas de tratamiento de información que le serán aplicables, la forma de acceder a las mismas y las características del Tratamiento que se pretende dar a los datos personales. DERECHOS QUE TIENEN FRENTE A LA COMPAÑÍA TODOS LOS TITULARES DE DATOS PERSONALES Todo proceso que conlleve el tratamiento por parte de cualquier área de la compañía de datos personales tanto de clientes, proveedores, empleados y en general cualquier tercero con el cual PANELESA S.A.S. sostenga relaciones comerciales y laborales deberá tener en cuenta e informarle de manera expresa y previa, por cualquier medio del cual se pueda conservar una constancia de su cumplimiento, los derechos que le asisten a ese titular de los datos, los cuáles se enuncian a continuación: 1. Derecho a conocer, actualizar, rectificar, consultar sus datos personales en cualquier momento frente a PANELESA S.A.S. respecto a los datos que considere parciales, inexactos, incompletos, fraccionados y aquellos que induzcan a error. 2. Derecho a solicitar en cualquier momento una prueba de la autorización otorgada a PANELESA S.A.S. 3. Derecho a ser informado por PANELESA S.A.S. previa solicitud del titular de los datos, respecto del uso que le ha dado a los mismos. 4. Derecho a presentar ante la Superintendencia de Industria y Comercio las quejas que considere pertinentes para hacer valer su derecho al Habeas Data frente a la compañía. 5. Derecho a revocar la autorización y/o solicitar la supresión de algún dato cuando considere que PANELESA S.A.S. no ha respetado sus derechos y garantías constitucionales. 6. Derecho a acceder en forma gratuita a los datos personales que voluntariamente decida compartir con PANELESA S.A.S., para lo cual la compañía en ayuda del área de tecnología, se encarga de conservar y archivar de forma segura y confiable los formatos de autorización de cada uno de los titulares de datos personales debidamente otorgadas. CASOS EN LOS CUALES PANELESA S.A.S. NO REQUIERE AUTORIZACIÓN PARA EL TRATAMIENTO DE LOS DATOS QUE TENGA EN SU PODER 1. Cuando la información sea solicitada a la compañía por una entidad pública o administrativa que esté actuando en ejercicio de sus funciones legales o por orden judicial. 2. Cuando se trate de datos de naturaleza pública debido a que éstos no son protegidos por el ámbito de aplicación de la norma. 3. Eventos de urgencia médica o sanitaria debidamente comprobadas. 4. En aquellos eventos donde la información sea autorizada por la ley para cumplir con fines históricos, estadísticos y científicos. 5. Cuando se trate de datos relacionados con el registro civil de las personas debido a que ésta información no es considerada como un dato de naturaleza privada. A QUIENES SE LES PUEDE ENTREGAR INFORMACIÓN POR PARTE DE PANELESAS.A.S. SIN NECESIDAD DE CONTAR CON AUTORIZACIÓN DE LOS TITULARES DE LOS DATOS · A los titulares de los datos, sus herederos o representantes en cualquier momento y a través de cualquier medio cuando así lo soliciten a PANELESA S.A.S. · A las entidades judiciales o administrativas en ejercicio de funciones que eleven algún requerimiento a la compañía para que le sea entregada la información. · A los terceros que sean autorizados por alguna ley de la república de Colombia. · A los terceros a los que el Titular del dato autorice expresamente entregar la información y cuya autorización sea entregada a PANELESA S.A.S. DEBERES QUE TIENE PANELESA S.A.S. RESPECTO A LOS TITULARES DE LOS DATOS PANELESA S.A.S. reconoce que los datos personales son propiedad de los titulares de los mismos y que únicamente tales personas podrán decidir sobre éstos. En este sentido, hará uso exclusivo para aquellas finalidades para las que sea facultado en los términos de la ley y en aras de lo anterior se permite informar los deberes que asume en su calidad de responsable del tratamiento: 1. La compañía deberá buscar el medio a través del cual obtener la autorización expresa por parte del titular de los datos para realizar cualquier tipo de tratamiento. 2. La compañía deberá informar de manera clara y expresa a sus clientes, empleados, proveedores y terceros en general de quienes obtenga bases de datos el tratamiento al cual serán sometidos los mismos y la finalidad de dicho tratamiento. Para ello, la compañía deberá diseñar la estrategia a través de la cual para cada evento, mecánica o solicitud de datos que se realice, informará a los mismos el respectivo tratamiento de que se trate. Algunos de estos medios pueden ser el envío de mensajes de texto, diligenciamiento de formatos físicos, a través de los sitios web de PANELESA S.A.S. entre otros. 3. La compañía debe informar a los titulares de los datos para cada caso, el carácter facultativo de responder y otorgar la respectiva información solicitada. 4. En todos los casos en los que se recopilen datos, se deberá informar los derechos que le asisten a todos los titulares respecto a sus datos. 5. La compañía debe informar la identificación, dirección física o electrónica y teléfono de la persona o área que tendrá la calidad de responsable del tratamiento. 6. La compañía, deberá garantizar en todo tiempo al titular de la información, el pleno y efectivo ejercicio del derecho al hábeas data y de petición, es decir, la posibilidad de conocer la información que sobre él exista o repose en el banco de datos, solicitar la actualización o corrección de datos y tramitar consultas, todo lo cual se realizará por conducto de los mecanismos de consultas o reclamos previstos en la presente política. 7. La compañía deberá conservar con las debidas seguridades los registros de datos personales almacenados para impedir su deterioro, pérdida, alteración, uso no autorizado o fraudulento y realizar periódica y oportunamente la actualización y rectificación de los datos, cada vez que los titulares de los mismos le reporten novedades o solicitudes. FINALIDADES EN LA CAPTURA, USO Y TRATAMIENTO DE DATOS PERSONALES PANELESA S.A.S. en el desarrollo de su objeto social y sus relaciones con terceros, entiéndase por estos clientes, empleados, proveedores, acreedores, aliados estratégicos, entre otros; recopila constantemente datos para llevar a cabo diversas finalidades y usos dentro de los cuales se pueden enmarcar: ● Fines administrativos, comerciales, promocionales, informativos, de mercadeo y ventas. ● Ofrecer todo tipo de servicios comerciales; así como realizar campañas de promoción, marketing, publicidad. ● Búsqueda de un conocimiento más cercano con todos sus clientes, proveedores, empleados y terceros vinculados. En relación con lo anterior, PANELESA S.A.S. podrá ejecutar las siguientes acciones: 1. Obtener, almacenar, compilar, intercambiar, actualizar, recolectar, procesar, reproducir y/o disponer de los datos o información parcial o total de aquellos titulares que le otorguen la debida autorización en los términos exigidos por la ley y en los formatos que para cada caso estime convenientes. 2. Clasificar, ordenar, separar la información suministrada por el titular de los datos. 3. Efectuar investigaciones, comparar, verificar y validar los datos que obtenga en debida forma con centrales de riesgo crediticio con las cuales se tengan relaciones comerciales. 4. Extender la información que obtenga en los términos de la ley de habeas data, a las empresas con las que contrata los servicios de captura, almacenamiento y manejo de sus bases de datos previas las debidas autorizaciones que en ese sentido obtenga. 5. Transferir los datos o información parcial o total a sus filiales, comercios, empresas y/o entidades afiliadas y aliados estratégicos. LA AUTORIZACIÓN A efectos de llevar a cabo los fines anteriormente mencionados, PANELESA S.A.S. requiere de manera libre, previa, expresa y debidamente informada de la autorización por parte de los titulares de los datos y para ello ha dispuesto mecanismos idóneos garantizando para cada caso que sea posible verificar el otorgamiento de dicha autorización. La misma podrá constar en cualquier medio, bien sea un documento físico, electrónico o en cualquier formato que garantice su posterior consulta a través de herramientas técnicas, tecnológicas y desarrollos de seguridad informática. La autorización es una declaración que informa al titular de los datos la siguiente información: ● Quien es el responsable o encargado de recopilar la información ● Datos recopilados ● Finalidades del tratamiento ● Procedimiento para el ejercicio de los derechos de acceso, corrección, actualización o supresión de datos ● Información sobre recolección de datos sensibles. DATOS RECOLECTADOS ANTES DE LA EXPEDICIÓN DEL DECRETO 1377 DE 2013 Para efectos de dar cumplimiento a lo dispuesto en el artículo 9º de la Ley 1581 de 2012, los Responsables del tratamiento de datos personales establecerán mecanismos para obtener la Autorización de los titulares o de quien se encuentre legitimado en los términos de la Ley. Estos mecanismos podrán ser predeterminados a través de medios técnicos que faciliten al titular su manifestación automatizada. La Autorización podrá otorgarse conforme a alguna de las siguientes opciones: (i) Por escrito, (ii) De forma verbal o (iii) Mediante conductas inequívocas del titular que permitan concluir de manera razonable que otorgó la autorización. En ningún caso el silencio podrá asimilarse a una conducta inequívoca. Así mismo, de conformidad a lo dispuesto en el artículo 10º del Decreto 1377 de 2013, PANELESA S.A.S. publico en diarios de amplía circulación nacional, el aviso de privacidad a través del cual comunico la existencia de la presente política, informando al respecto a la Superintendencia de Industria y Comercio. Conforme se indica en este Decreto, si en el término de treinta (30) días hábiles a partir de la implementación del anterior mecanismo, los titulares no contactaron al RESPONSABLE o ENCARGADO para solicitar la supresión de sus datos personales, el RESPONSABLE y ENCARGADO podrán continuar realizando el Tratamiento de los datos personales contenidos en sus bases de datos para la finalidad o finalidades previstas e indicadas en la política de tratamiento de la información. PROTECCION DATOS PERSONALES DE MENORES DE EDAD Y ADOLESCENTES En atención a lo dispuesto en la Ley Estatutaria 1581 de 2012 y el Decreto Reglamentario 1377 de 2013, PANELESA S.A.S. Asegura que el Tratamiento de los datos personales de niños, niñas y adolescentes será realizado respectando sus derechos, razón por la cual, en las actividades comerciales y de mercadeo que realice PANELESA S.A.S. deberá contar con la autorización previa, expresa e informada del padre o la madre o del representante legal de la niña, niño o adolescente. FORMA DE PROCEDER RESPECTO A LAS CONSULTAS Y SOLICITUDES HECHAS POR LOS TITULARES DE LOS DATOS Todo titular de datos personales tiene derecho a realizar consultas y elevar solicitudes a la compañía respecto al manejo y tratamiento dado a su información. A). PROCEDIMIENTO PARA EL TRÁMITE DE RECLAMOS O SOLICITUDES: Toda solicitud, petición, queja o reclamo (PQR) que sea presentada a PANELESA S.A.S. por parte de cualquier titular o sus causahabientes respecto al manejo y tratamiento dado a su información será resuelta de conformidad con la ley regulatoria al derecho al habeas data y será tramitado bajo las siguientes reglas: 1. La petición o reclamo se formulará mediante escrito o cualquier otro de los medios definidos en la presente política para tal fin, dirigido a PANELESA S.A.S., con la identificación del titular, la descripción de los hechos que dan lugar al reclamo, la dirección o medio a través del cual desea obtener su respuesta, y si fuere el caso, acompañando los documentos de soporte que se quieran hacer valer. En caso de que el escrito resulte incompleto, la compañía solicitará al interesado para que subsane las fallas dentro de los cinco (5) días siguientes a la recepción del reclamo. Transcurridos dos meses desde la fecha del requerimiento, sin que el solicitante presente la información requerida, se entenderá que ha desistido de la reclamación o petición. 2. Una vez recibida la petición o reclamo completo, la compañía incluirá en el registro individual en un término no mayor a dos (2) días hábiles una leyenda que diga \"reclamo en trámite\" y la naturaleza del mismo. Dicha información deberá mantenerse hasta que el reclamo sea decidido. 3. El solicitante recibirá una respuesta por parte de PANELESA S.A.S. dentro de los diez (10) días hábiles siguientes contados a partir de la fecha en la cual ha tenido conocimiento efectivo de la solicitud. 4. Cuando no fuere posible atender la petición dentro de dicho término, se informará al interesado, expresando los motivos de la demora y señalando la fecha en que se atenderá su petición, la cual en ningún caso podrá superar los cinco (5) días hábiles siguientes al vencimiento del primer término. B). CONSULTAS: La Política de manejo de la información personal por parte de PANELESA S.A.S. y los derechos básicos que los titulares de los datos tienen en relación con la misma podrá ser consultada a través de los siguientes medios: · www.panelesa.com Cualquier consulta que tenga un titular sobre su información o datos personales o cuando considere necesario instaurar una solicitud de información o considere que sus derechos han sido vulnerados en relación con el uso y el manejo de su información; podrá hacerlo a través del siguiente correo electrónico: atencionalcliente@panelesa.com Si dentro de los diez (10) días señalados, no fuere posible para la compañía atender la consulta, el área correspondiente deberá informar al interesado, los motivos de la demora e indicarle la fecha en que se atenderá la misma, la cual en ningún caso podrá superar los cinco (5) días hábiles siguientes al vencimiento del primer término. C). RESPONSABLE DEL TRATAMIENTO: PANELESA S.A.S. Tiene la calidad de responsable del tratamiento, a través de la presente política se permite informar sus datos de identificación: Razón social: PANELESA S.A.S. NIT: 811.038.400-1 Domicilio: Carrera 50 100 B Sur 340 La Estrella, Antioquia. Persona o dependencia responsable de la atención de peticiones, consultas y reclamos: el área encargada de recibir y canalizar todas las solicitudes e inquietudes es la Gerencia Comercial a través del correo electrónico atencionalcliente@panelesa.com D. ENCARGADO DEL TRATAMIENTO: Eventualmente, PANELESA S.A.S. Podrá tener la calidad de ENCARGADO DEL TRATAMIENTO, caso en el cual los datos de identificación son los siguientes: Razón social: PANELESA  S.A.S. NIT: 811.038.400-1 Domicilio: Carrera 50 100 B Sur 340 La Estrella, Antioquia. Persona o dependencia responsable de la atención de peticiones, consultas y reclamos: el área encargada de recibir y canalizar todas las solicitudes e inquietudes es la Gerencia Comercial a través del correo electrónico atencionalcliente@panelesa.com POLITICAS DE SEGURIDAD INFORMÁTICA Para PANELESA S.A.S. es fundamental y prioritario adoptar medidas técnicas, jurídicas, humanas y administrativas que sean necesarias para procurar la seguridad de los datos de carácter personal protegiendo la confidencialidad, integridad, uso, acceso no autorizado y/o fraudulento. Asimismo, se permite informar que internamente la compañía ha implementado protocolos de seguridad de obligatorio cumplimiento para todo el personal con acceso a datos de carácter personal y a los sistemas de información. Las políticas internas de seguridad bajo las cuales se conserva la información del titular para impedir su adulteración, pérdida, consulta, uso o acceso no autorizado o fraudulento, son las siguientes: 1. Políticas en la Infraestructura tecnológica perimetral en la red de datos (Sistema de prevención de intrusos (IPS), Firewalls, correo seguro, control de contenido, control de acceso a la red NAC, antivirus y anti X). 2. Políticas en la Infraestructura tecnológica y políticas de control de acceso a la información, aplicaciones y bases de datos (Plataforma MS directorio activo, módulos de seguridad, cifrado PGP). 3. Políticas de implementación tecnológica que minimizan el riesgo de las plataformas críticas ante desastres (DRP Disaster Recovery Plan). 4. Políticas de implementación tecnológica que protegen los computadores y servidores de la organización de malware. 5. Políticas de implementación tecnológica que impide la utilización de dispositivos USB de almacenamientos no autorizados. 6. Políticas de implementación tecnológica que controla el envío y transmisión electrónica caracterizada como confidencial (DLP - Data Loss Prevention-, Transfer). 7. Uso de diferentes ambientes en las plataformas críticas, para que desarrolladores y consultores puedan trabajar sin problema (DEV desarrollo, QA calidad y PDN Productivo). 8. Políticas de implementación tecnológica que respalda la información contenida en las distintas plataformas. 9. Política escrita sobre seguridad de la información y uso de las herramientas de información. 10. Acuerdo de confidencialidad con proveedores y terceros. 11. Cláusula de confidencialidad en los contratos laborales de empleados. 12. Procedimientos de Autocontrol y respuesta a Auditoría interna y Externa. 13. En todos los eventos que se realizan, en los cuales se captura información del cliente se incluye el párrafo de Habeas data, con sus respectivas implicaciones. 14. Aviso Habeas Data. Por el hecho de participar en el Evento, todo participante declara conocer y autorizar de manera libre, previa, voluntaria, expresa y debidamente informada a PANELESA S.A.S. para recolectar, registrar, procesar, difundir, compilar, intercambiar, actualizar y disponer de los datos o información parcial que le suministró, y a efectos de participar en el Evento; así como para transferir dichos datos o información parcial o total a sus comercios y empresas con el fin de que PANELESA S.A.S. pueda ofrecer sus productos y/o servicios a sus clientes de una manera más personalizada y directa, y además a contactar a la persona en caso tal de resultar ser el ganador del Evento, a hacer envío de información publicitaria de las marcas propias, mailing, sms, correo directo y, comercializar todos los datos e información que de forma voluntaria suministró al momento de participar en el Evento. La utilización de la base de datos será desde el inicio del Evento hasta el día en que PANELESA S.A.S. entre en liquidación. PANELESA S.A.S. garantiza que da cumplimiento a la protección de los datos personales suministrados por sus clientes en virtud de lo dispuesto en la normatividad regulatoria del derecho al HABEAS DATA, para lo cual se permite informar: 1. Que el derecho de hábeas data es aquel que tiene toda persona de conocer, actualizar y rectificar de forma gratuita la información que se haya recogido sobre ella en archivos y bancos de datos de naturaleza pública o privada. 2. Que el cliente como titular de la información podrá acceder a sus datos en cualquier momento, por lo cual podrá modificarlos, corregirlos , actualizarlos, revocar y solicitar prueba de la autorización dada si así lo considera a través de este medio o a través de las oficinas de Servicio al Cliente de los almacenes en todo el país. 3. Que el cliente como titular de la información tiene la facultad o no de informar aquellos datos que libremente disponga y de elevar solicitudes respecto al uso que se la haya dado a sus datos. 4. Que, para el ejercicio pleno y efectivo de este derecho por parte de todos sus clientes, PANELESA S.A.S. ha dispuesto los siguientes medios a través de los cuales podrán presentar sus solicitudes, quejas y/o reclamos: email: atencionalcliente@panelesa.com Teléfono: (+57) 317 355 6309. PROTECCIÓN DE DATOS De conformidad con lo establecido en Ley 1581 de 2012 y sus decretos reglamentarios de Protección de Datos de Carácter Personal, por el que se regula el derecho de información en la recolección de datos le informamos lo siguiente: - Los datos de carácter personal que nos ha suministrado en esta y otras comunicaciones mantenidas con usted serán objeto de tratamiento en los ficheros responsabilidad de PANELESA S.A.S. - La finalidad del tratamiento es la de gestionar de forma adecuada la prestación del servicio que nos ha requerido. Asimismo, estos datos no serán cedidos a terceros, salvo las cesiones legalmente permitidas. - Los datos solicitados a través de esta y otras comunicaciones son de suministro obligatorio para la prestación del servicio. Estos son adecuados, pertinentes y no excesivos. - Su negativa a suministrar los datos solicitados implica la imposibilidad prestarle el servicio. - Asimismo, le informamos de la posibilidad de ejercitar los correspondientes derechos de acceso, rectificación, cancelación y oposición de conformidad con lo establecido en la Ley 1581 de 2012 ante PANELESA S.A.S. como responsables del manejo de los datos aquí suministrados. Los derechos mencionados los puede ejercitar a través del correo electrónico atencionalcliente@panelesa.com")
                            font.pixelSize: 16
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Button {
                    id: buttonAboutCoffeePie
                    x: 0
                    y: 102
                    width: 283
                    height: 66
                    visible: true
                    text: qsTr("")
                    flat: true

                    Text {
                        id: lblAboutCoffeePie
                        x: 8
                        y: 12
                        width: 275
                        height: 46
                        visible: true
                        color: "#f2f8f9"
                        text: qsTr("Qué es Coffee Pie®")
                        font.pixelSize: 22
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                    }

                    Connections {
                        target: buttonAboutCoffeePie
                        function onClicked() {
                            boxAboutCoffeePie.visible = true
                            boxSliceDefinition.visible = false
                            boxFirstSteps.visible = false
                            boxIntermediateUser.visible = false
                            boxAdvancedUser.visible = false
                            boxTermsAndConditions.visible = false
                            boxPrivacyPolicy.visible = false
                        }
                    }
                }

                Rectangle {
                    id: boxTermsAndConditions
                    x: 282
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"
                    ScrollView {
                        id: scrollViewTermsAndConditions
                        x: 0
                        y: 0
                        width: 1064
                        height: 546
                        Text {
                            id: txtTermsAndConditions
                            x: 16
                            y: 17
                            width: 1032
                            height: 511
                            color: "#f2f8f9"
                            text: qsTr("POR FAVOR LEA BIEN ESTOS TÉRMINOS Y CONDICIONES YA QUE CONSTITUYEN UN ACUERDO LEGAL ENTRE USTED Y GRUPO 3P1 COLOMBIA\n\n \n\nEstos Términos y Condiciones rigen todas las Ventas de Productos y Servicios que ofrece PANELESA™, marca del GRUPO 3P1 COLOMBIA, el cual opera como Comercializadora Mayorista Internacional, Promotora Comercial e Integrador en su calidad de Agente Comercial con responsabilidad limitada, en adelante GRUPO 3P1, en representación de las Empresas del Grupo en calidad de Fabricantes, Constructores, Ensambladores, Instaladores, Principalmente de los Sectores Industrial, Constructivo y Cadena de Frío, ante el Cliente en calidad de Comprador. Todas las Ventas están sujetas y expresamente condicionadas a los Términos y Condiciones contenidas en éste documento, siendo obligatoria la no variación de estos, salvo autorización expresa de GRUPO 3P1:\n\n \n\n1) INTERPRETACIÓN: Las disposiciones señaladas se interpretarán de la manera más amplia y fidedigna posible, limitadas únicamente por las leyes imperativas de la República de Colombia.\n\n2) VALIDEZ DE LA OFERTA: La validez de todo documento de oferta es de cinco (5) días calendario a partir de la fecha de emisión del documento. Debido a la volatilidad de la Tasa Representativa del Mercado (TRM), GRUPO 3P1 no se compromete a sostener los precios luego de transcurrido éste periodo y se reserva el derecho a reemplazar dicho documento, actualizando los precios según considere necesario.\n\n3) PRECIOS Y AJUSTES: Los precios indicados en el rostro del documento de oferta de GRUPO 3P1 sólo se aplican a los Productos programados para su envío, como se detalla en el documento de oferta y reconocidos por GRUPO 3P1. No obstante, GRUPO 3P1 se reserva el derecho de aumentar los precios mediante notificación al Cliente de los envíos programados para entregas superiores a treinta (30) días a partir de la fecha de la Orden de Compra del Cliente. Siempre y cuando los Productos no sean \"Especiales\" o “Fabricados a la Medida”, el Cliente tendrá cinco (5) días a partir de la fecha de dicha notificación para cancelar su orden sin cargo, con respecto a cualquiera de los Productos no programados para su envío antes de la fecha de vigencia del aumento de los precios. Los descuentos comerciales son negociables según alcance y magnitud del proyecto.\n\n4) IMPUESTOS: Además de los precios indicados, el Cliente deberá pagar a GRUPO 3P1 el monto de los impuestos de venta, uso u otros impuestos especiales aplicados a la Venta de los Productos, para que GRUPO 3P1 se haga responsable y pague estos impuestos cuando sea requerido por la Ley, a menos que el Cliente proporcione previa y oportunamente a GRUPO 3P1 el certificado de exención fiscal correspondiente junto con la orden de compra. GRUPO 3P1 no se hace responsable por la omisión del detalle de los impuestos en los documentos, cambio, aumento o nuevos conceptos aplicados por entidades estatales o autoridades competentes, los cuales son adicionales a los precios mencionados.\n\n5) ORDENES DE COMPRA: Independientemente de si el Cliente ordena los Productos o Servicios por medio de ordenes escritas, ordenes telefónicas, órdenes verbales o pedidos electrónicos, rigen los Términos y Condiciones estipulados en éste documento. Se entiende que la persona que efectúa el Pedido o emite la Orden de Compra a nombre del Cliente cuenta con las debidas facultades para representar al Cliente ante GRUPO 3P1, y que, por lo tanto, ésta Orden de Compra compromete al Cliente. La fecha límite para órdenes de compra es el 15 de diciembre del año en vigencia, de lo contrario, será necesario actualizar los precios según el índice de precios al consumidor (IPC), inflación y tasas representativas del mercado del siguiente año. Todos los Pedido y Comunicaciones Oficiales que el Cliente realice a las Empresas del Grupo deberán ser tramitadas a través de los canales autorizados con copia al correo electrónico panelesa@panelesa.com, de no hacerlo, no se prestará más la Asesoría Comercial y el Cliente perderá automáticamente todas las garantías, incluyendo Pedidos u Órdenes de Compra anteriores de forma retroactiva, y por ende, deberá asumir todos los riesgos por su propia cuenta y asumir los costos de reparación o cambio de los productos que no hayan sido tramitados por dichos canales. Ocultar información de órdenes de compra, pedidos, adendas, otros sí, ordenes de servicio, etc., permitirá a GRUPO 3P1 el cobro de las respectivas comisiones, más los intereses moratorios a la tasa máxima autorizada por la Ley.\n\n6) OBRA CIVIL: Los documentos de oferta, como Cotización o Presupuesto Estimado de Obra, NO contemplan implícitamente procesos de Obra Civil, incluyendo, pero no limitando, demoliciones, excavaciones, movimientos de tierras, cimientos, rellenos, zapatas, vigas, vaciado de pisos, cárcamos, medias cañas, desagües, redes hidrosanitarias, acometidas, redes eléctricas, estructuras, mampostería, pintura, disposición de residuos sólidos, etc. GRUPO 3P1 no se hace responsable por la omisión de dichos conceptos en la oferta y no está obligado a ejecutarlos a menos que estén claramente especificados y valorados en el rostro del documento. Todos los presupuestos de obra son estimados y se liquidarán con base en las cantidades reales de obra ejecutadas según las tarifas o precios unitarios, los cuales pueden variar dentro de un margen razonable según las condiciones reales de obra.\n\n7) ACEPTACIÓN: Con la recepción de una aceptación expresa por parte del Cliente, la Orden de Compra física, electrónica o verbal emitida por el Cliente, y la emisión por parte de GRUPO 3P1 de una confirmación del Pedido, se entenderá celebrado un Contrato de Venta de acuerdo con el contenido del Pedido u Orden de Compra. El Pedido mínimo para productos con características especiales será definido en cada caso por GRUPO 3P1. La lámina de acero estándar es de color Banco Almendra Calibre 0,38mm ±0,03mm (C28 Sistema Anglosajón), PUR densidad nominal 38Kg/m³ ±2Kg/m³. Las puertas ofrecidas son de fabricación nacional según el estándar de GRUPO 3P1, cualquier especificación diferente, como puertas importadas según estándar europeo, está sujeta a disponibilidad de inventario y podría aumentar el precio y tiempo de entrega hasta en noventa (90) días calendario contados a partir de radicada la Orden de Compra, confirmadas las dimensiones y realizado el Anticipo. El servicio de instalación puede ser prestado a partir de 500m², siempre y cuando GRUPO 3P1 cuente en el momento con la fuerza laboral disponible, de lo contrario, se recomendará a un Colega o Empresa del Grupo, o se suministrarán el Manual Técnico de Instalación y se sugerirán los Accesorios necesarios para su correcta instalación. GRUPO 3P1 no está obligado a dar capacitación o entrenamiento. Tolerancias aceptables en el largo ±20mm, en el ancho ±10mm, en el espesor ±5mm, en densidad ±3%, en tonalidad de pintura entre lotes ±5%. Al momento de la aprobación, el cliente debe enviar el Registro Único Tributario (RUT), Cámara de Comercio y Cédula del Representante Legal actualizados al correo de recepción general panelesa@panelesa.com para la generación del Pedido y Facturación Electrónica desde la/s respectiva/s empresa/s del Grupo Empresarial, según se haya negociado el Contrato.\n\n8) CONFLICTO ENTRE LA ORDEN DE COMPRA Y LOS TÉRMINOS Y CONDICIONES: En caso de existir alguna discrepancia entre la Orden de Compra y los Términos y Condiciones, estos términos prevalecen, excepto cuando GRUPO 3P1 hubiese aceptado expresamente y confirmado por escrito la aceptación de estos términos en discrepancia. GRUPO 3P1 no aceptará términos y condiciones contenidos en documentos provenientes del Cliente, tales como Solicitudes de Cotización, Solicitud de Oferta, Órdenes de Compra y documentos similares que modifiquen o realicen cualquier cambio a los Términos y Condiciones de GRUPO 3P1, y no tendrán ninguna validez ni fuerza obligante para GRUPO 3P1, ni las Empresas del Grupo, ni sus respectivos proveedores, los cuales actuarán según su alcance y de acuerdo con su Razón Social o “Core Business”. No existirá responsabilidad de GRUPO 3P1 en los errores tipográficos o administrativos realizados en las citas, órdenes o publicaciones, los cuales están sujetos a corrección.\n\n9) CAMBIOS O MODIFICACIONES AL PEDIDO: Siempre y cuando no se haya iniciado la fabricación de los Productos y estos no sean \"Especiales\" o “Fabricados a la Medida”, los Pedidos que surjan a continuación pueden ser cambiados o modificados por un acuerdo escrito firmado por el Cliente y GRUPO 3P1, donde se establecen los cambios particulares que se hagan, y en tal caso, los cambios en el precio y tiempo de entrega.\n\n10) CANCELACIÓN DE LA ORDEN DE COMPRA O PEDIDO: El Cliente no puede cancelar la Orden de Compra a menos que la cancelación sea acordada por escrito expresamente por GRUPO 3P1. En tal caso, GRUPO 3P1 notificará al Cliente de los cargos totales de dicha cancelación, y el Cliente se compromete a pagar tales cargos, incluyendo, pero no limitando, el almacenamiento y costos de envío, los costos de producción de materiales no convencionales, los costos de compra de materiales no retornables, los gastos de anulación cargados a GRUPO 3P1 o a las Empresas del Grupo por sus respectivos proveedores, y cualquier otro costo resultante de la cancelación autorizada por GRUPO 3P1 de dicha Orden de Compra.\n\n11) PAGO Y ANTICIPO: Los Plazos de Producción y Entrega sólo comienzan a contar una vez sean autorizadas las dimensiones y especificaciones por parte del Cliente, realizado y verificado el Anticipo. La forma de pago para clientes que no hayan diligenciado una autorización de consulta a centrales de riesgo es de Estricto Contado. El Anticipo para suministros simples será del 50% y el restante 50% deberá ser cancelado previo al envío o recogida de los Productos. Para Proyectos Constructivos o Instalación de los Productos, el Pago por Defecto será: Anticipo del 50%, 40% de Avances de Obra y el 10% restante contra Acta de Entrega a Satisfacción, una vez sea recibido por el Cliente, a menos que en el rostro del documento se especifiquen los términos y condiciones de pago pactados. El Cliente deberá hacer el pago como sean hechas las entregas por GRUPO 3P1, excepto si se requiere un depósito de una Orden Especial, explícitamente definido sobre el rostro de la Orden de Compra. El pago de todas las cantidades facturadas al Cliente será en moneda colombiana (COP), a menos que en el rostro del documento se indique la moneda (USD, EUR, etc). En el caso que la entrega se haga a cuotas, las anualidades de amortización serán facturadas y pagadas por separado a su vencimiento por factura sin tener en cuenta las entregas posteriores. En el caso de los proyectos constructivos, el Cliente deberá ceñirse a los porcentajes de abono pactados, independientemente de las nimiedades o pormenores que queden pendientes. Todos los presupuestos son estimados y se liquidarán según las condiciones reales de obra. GRUPO 3P1 deja constancia de que los Productos son de su propiedad hasta tanto no sean debidamente pagados. En el caso de No Pago o Mora en el Pago, GRUPO 3P1 se reserva el pleno derecho, sin previo aviso ni órdenes judiciales, de retirar los Productos o bienes de las instalaciones del cliente o lugar de la obra con la intervención y respaldo de la fuerza pública, hasta tanto dichos Productos no sean total y debidamente cancelados.\n\n12) FACTURACIÓN: Por defecto, se realizará una Factura de Venta Electrónica desde la respectiva Empresa del Grupo encargada de provisionar el bien o servicio, por cada una de las Órdenes de Compra del Cliente. El Cliente puede solicitar ajustes en la fecha de facturación, la consolidación de múltiples Órdenes de Compra en una única Factura de Venta, o facturar ítems individualmente en Facturas de Venta separadas; Para ello debe hacerlo por escrito al menos cinco (5) días antes de la primera fecha de facturación entre dichas Órdenes de Compra. Una vez impresa la factura, GRUPO 3P1 y las Empresas del Grupo se reservan el derecho a generar Nota de Contabilidad, anular la Factura de Venta o corregirla, según consideren necesario, no por ello limitando o afectando los compromisos de pago del Cliente. En el caso de los Proyectos Constructivos, GRUPO 3P1 se reserva el derecho a liquidar y facturar con base en las cantidades reales de obra ejecutadas, desviándose del presupuesto inicial sólo dentro del margen razonable. GRUPO 3P1 se reserva el derecho a generar y utilizar centros de costos en función de los proyectos para hacer seguimiento y trazabilidad de los envíos o remisiones para efectos de control. Los documentos de recepción que no puedan ser firmados con letra legible por ausencia de un funcionario autorizado del cliente en un proyecto, o cualquier otra causa, serán firmados y verificados por el funcionario de GRUPO 3P1 a cargo y posteriormente verificados en la liquidación de la obra. GRUPO 3P1 no asume los desperdicios generados en obra, bien sea por la falta de precisión de los planos o medidas otorgados por el Cliente, defectos en la estructura no fabricada por GRUPO 3P1, cambios imprevistos o cualquier otra causa más allá del control razonable de GRUPO 3P1, y se reserva el derecho a facturar dichos conceptos con previa notificación al Cliente.\n\n13) RESPONSABILIDAD FINANCIERA: En el caso de que el Cliente no cumpla con las condiciones de pago para cualquier envío de Productos, o si GRUPO 3P1 tuviera una duda razonable en cualquier momento de la capacidad de pago del Cliente por los Productos ordenados, GRUPO 3P1 podrá elegir sin responsabilidad civil, (a) cambiar los términos de pago o (b) aplazar aún más la producción y los envíos hasta un cumplimiento satisfactorio del Cliente en cuanto a la capacidad financiera, y tal cambio o aplazamiento no afectará cualquier otra reclamación por daños y perjuicios, que por otra parte GRUPO 3P1 pueda tener contra el Cliente. En el caso de incumplimiento en las obligaciones el Cliente podrá ser reportado a las centrales de riesgo, se generarán intereses por mora a la tasa máxima legal autorizada y bodegaje por los productos no retirados oportunamente.\n\n14) ENVÍO: Los documentos de oferta no incluyen implícitamente los precios de envío, a menos que se haya acordado por escrito lo contrario por las partes, el Cliente es responsable de retirar los productos de las instalaciones de GRUPO 3P1 o las respectivas Empresas del Grupo, excepto si en el rostro del documento fue pactado el transporte de las mercancías, en cuyo caso el método de embalaje y envío de los Productos será a discreción de GRUPO 3P1. En ninguna circunstancia el Cliente podrá exigir a GRUPO 3P1 despachar Productos o ejecutar Servicios durante los lapsos de descanso establecidos por la ley y en relación con el reglamento interno de trabajo de GRUPO 3P1 y las Empresas del Grupo.\n\n15) ENTREGA: Si no se especifica tiempo de entrega en el rostro del documento éste será por defecto de treinta (30) días hábiles para Suministro de Productos Estándar, sesenta (60) días hábiles para Suministro e Instalación de Productos Estándar, (90) días hábiles para Proyectos Constructivos y “Fabricaciones Especiales o a la Medida”, por cada mil (1.000m²) metros cuadrados de Panel Sandwich o equivalente, o por cada cien mil dólares (100.000 USD) en el valor de venta antes de impuestos. GRUPO 3P1 se reserva el derecho de hacer la entrega a plazos. El retraso en la entrega de cualquier plazo no liberará al Cliente de su obligación a aceptar las entregas restantes. Si una entrega se retrasa como resultado de cualquier acción u omisión del Cliente, GRUPO 3P1 podrá facturar al Cliente los Productos a partir de la fecha de entrega programada y podrá cobrar al Cliente por el almacenamiento o bodegaje y otros gastos incurridos a causa de la demora. La obligación de GRUPO 3P1 con respecto a la entrega termina a partir de la primera cesión de los Productos a la empresa de transporte competente en las instalaciones de GRUPO 3P1. A partir de entonces, todo riesgo de daño, descargue, pérdida o retraso en el transporte correrán a cargo del Cliente, a menos que la Instalación sea previamente pactada, y en tal caso, la responsabilidad de GRUPO 3P1 termina en las instalaciones del Cliente o en el Lugar de Instalación u Obra, según corresponda. Todo Proyecto Constructivo debe concluir con un Acta de Entrega, la cual debe ser firmada por el cliente una vez sean recibidos los Productos y Servicios a satisfacción. GRUPO 3P1 no se hace cargo de los costos de Cargue y Descargue, ni cargos adicionales ocasionados en el transporte, que por negligencia u omisión del Cliente sean generados, y se reserva el derecho a facturar dichos conceptos con una nueva Orden de Compra y su respectiva Factura.\n\n16) RETRASO EXCUSABLE: GRUPO 3P1 no será responsable de ninguna pérdida, daño o penalización como consecuencia de cualquier retraso en la entrega, falla de fábrica, o posterior mal funcionamiento debido a cualquier causa más allá del control razonable de GRUPO 3P1, incluyendo, pero no limitando, actos del Cliente, embargo u otros actos gubernamentales, regulación o solicitud que afecte el ejercicio de la actividad, incendio, explosión, accidente, robo, vandalismo, disturbios, insurrección, sabotaje, inundaciones, dificultades laborales, rayos, tormentas de viento, u otras catástrofes naturales, clima inusualmente severo, accidentes, epidemias, restricciones de cuarentena, actos de locales, estatales o nacionales, gobiernos o agencias públicas, disputas laborales, escasez, energía o carencias materiales, fallas de servicios públicos, retrasos de comunicación, amenazas, actos de terrorismo, retrasos de un proveedor de GRUPO 3P1, y cualquier otra causa de fuerza mayor o más allá del control razonable sin la culpa o negligencia de GRUPO 3P1. En el caso de la demora, la fecha de entrega se diferirá durante un período igual al tiempo perdido a causa de la demora.\n\n17) INSPECCIÓN: Inmediatamente después de la recepción de los bienes, el Cliente deberá inspeccionar los mismos y notificar a GRUPO 3P1 por escrito de cualquier reclamación por carencias, defectos o daños, y se ocupará de las mercancías para las instrucciones de GRUPO 3P1 relativos a su disposición. Si el Cliente dejara de notificarlo a GRUPO 3P1 el día que los bienes han sido recibidos por el Cliente, se considerará que dichos bienes cumplen con los términos y condiciones del mismo y habrán sido irrevocablemente aceptados por el Cliente. Si el Cliente presenta una queja o reclamo luego de éste lapso aplican todas las condiciones y restricciones de los Términos y Condiciones de Garantía.\n\n18) GARANTÍA: GRUPO 3P1 únicamente garantiza los Productos vendidos al Cliente a través de los medios oficiales haciendo uso de la garantía otorgada por el fabricante o contratista proveedor del servicio correspondiente, hasta el grado específicamente establecido en los Términos y Condiciones de Garantía, atendiendo estrictamente los mantenimientos preventivos, procedimientos y recomendaciones emitidos a través de cualquier medio por GRUPO 3P1 y las Empresas del Grupo, o implícitamente contenidos en el manual del usuario o instructivo. Todos los Productos manufacturados por las Empresas del Grupo tienen una garantía limitada por defectos de fabricación  mínima de doce (12) meses calendario en Condiciones Normales (Dentro de las condiciones anormales están incluidas, pero no limitadas: Zonas Costeras a menos de 50 Km del mar, ambientes altamente salinos, tundras, desiertos, humedades inferiores al 50% o superiores al 90%, zonas de limpieza con agentes altamente corrosivos, zonas de vientos inusualmente severos, temperaturas sobre los 40°C, zonas con alto nivel de toxicidad o radiación ionizante), a excepción de los Cuartos Fríos, en cuyo caso dependerá del plan de mantenimiento preventivo/predictivo contratado con las Empresas del Grupo; De no ser contratado uno de estos planes con una compañía profesional o vinculado un Técnico de Mantenimiento capacitado por ACAIRE, GRUPO 3P1 no podrá garantizar el óptimo funcionamiento y máxima eficiencia energética de los equipos. En ningún caso la garantía incluye partes de desgaste, sobrecargas eléctricas, exposición a agentes corrosivos o ambientes salinos, mala instalación, manipulación negligente por parte del Cliente o de terceros. Si los Productos no son instalados por GRUPO 3P1, ésta no se hace responsable por los defectos o daños de cualquier índole ocasionados durante o después de la instalación. Si GRUPO 3P1 no es el encargado de la fabricación e instalación de la estructura de soporte, este no se hace responsable de los defectos de instalación que puedan surgir a continuación y podrá facturar los importes que considere necesarios para su corrección, reemplazo, desinstalación, reinstalación y procedentes. GRUPO 3P1 se reserva el derecho a revisar exhaustivamente los Productos declarados como defectuosos, establecer el tiempo que considere pertinente para determinar las causas del daño y aprobar o denegar la garantía de los Productos que crea hayan sido manipulados con negligencia o expuestos a condiciones extremas, tales como golpes, caídas, sobrecargas eléctricas, humedad o cualquier otra causa más allá del uso razonable. La marca comercial de los Productos en los documentos de oferta puede variar según su disponibilidad y capacidad de producción de las Empresas del Grupo, GRUPO 3P1 se reserva el derecho a reajustar el valor y tiempo de entrega de dichos Productos notificando previamente al Cliente para su respectiva aprobación. Es completamente normal e inevitable que surjan pequeñas abolladuras, burbujas, rayones o desprendimiento del recubrimiento, totalmente intrascendentes para la operación de los productos, fruto del transporte, la manipulación, desplazamiento del personal, uso de herramientas, colocación de objetos, cambios de temperatura abruptos y otras condiciones climáticas adversas; Siempre y cuando no comprometan la estabilidad de la obra ni la funcionalidad de los productos, estos no constituyen un argumento válido para una reclamación por Garantía, ni para aplazar la Liquidación o Facturación, ya que estos pueden ser reparados, retocados o repintados en Obra, sin que esto afecte la idoneidad de los mismos. En caso de una reclamación válida por garantía, ésta se tramitará directamente con la fábrica, empresa o contratista correspondiente de fabricar el producto o proveer el servicio respectivo, en todo caso siguiendo las directrices e instrucciones de GRUPO 3P1.\n\n19) DEVOLUCIONES Y RECLAMOS: Para la devolución de los productos, se deberá obtener la autorización por escrito de GRUPO 3P1 antes de la devolución de los mismos. Tras la verificación de GRUPO 3P1 del defecto, ésta se reserva la elección de reparar, sustituir o emitir crédito a consideración de la misma, sólo por concepto del Producto Defectuoso. GRUPO 3P1 tendrá derecho antes de la devolución, de inspeccionar en el almacén del Cliente cualquier Producto afirmado sea defectuoso o no conforme y tramitar la correspondiente garantía con el fabricante o proveedor del servicio. El riesgo de daño o pérdida a cualquier Producto devuelto a GRUPO 3P1 para el ajuste permanecerán con el Cliente hasta tanto sean recibidos por GRUPO 3P1. Los gastos de envío de los Productos devueltos serán asumidos por GRUPO 3P1 sólo para los Productos reparados o reemplazados en virtud de la Garantía dentro del territorio nacional, de lo contrario, dicho cargo correrá a cargo del Cliente. Las reclamaciones por la falta de materiales, errores de facturación o no recibo del transporte deberán hacerse por escrito dentro de los tres (3) días hábiles siguientes a la recepción de la Factura de Venta.\n\n20) INSTALACIÓN DEL PRODUCTO: En los Contratos cuyo alcance comprenda la Instalación, el Cliente deberá asignar los espacios adecuados con sus respectivas medidas de seguridad para el almacenamiento temporal de los Productos, materiales y herramientas consignadas en Obra; Si el Cliente no puede suministrar dichas condiciones deberá hacerse cargo de los costos de almacenamiento externo, daño o pérdida de dichos Productos y Equipos. Los tiempos muertos perdidos sin culpa o negligencia de GRUPO 3P1, serán anotados en la Minuta de Obra y tenidos en cuenta en la liquidación del proyecto para su posterior facturación. El tiempo estimado de entrega incluido en el rostro del documento es un aproximado con base en la experiencia del asesor en contratos similares, por lo que GRUPO 3P1 no se hace responsable de los costos generados por el retraso causado por situaciones ajenas a su control, y se podrán facturar dichos cargos extras e imprevistos. El Cliente se compromete a desagraviar y mantener indemne a GRUPO 3P1, sus directores, funcionarios, agentes y empleados contra todos los gastos, pérdida, honorarios de abogados, costos, daños o responsabilidad derivada de cualquier reclamación, acción relacionada con, o derivada de cualquier reclamación por defectos de instalación del Producto. A petición de GRUPO 3P1, el Cliente deberá defender por su cuenta todas las reclamaciones o acciones, dejando constancia de que GRUPO 3P1 tendrá derecho a elegir participar o no en dicha defensa.\n\n21) LIMITACIÓN DE RESPONSABILIDAD: La responsabilidad de GRUPO 3P1 para los Productos Defectuosos o no conformes, ya sea basado en el incumplimiento de la garantía, la fabricación negligente o compromiso del Producto, se limita exclusivamente a la reparación o reemplazo, a elección de GRUPO 3P1, de los respectivos Productos Defectuosos. GRUPO 3P1 no asume riesgo y no estará sujeto a ninguna responsabilidad por cualquier daño o pérdida resultante del uso o aplicación específica de los Productos. La responsabilidad de GRUPO 3P1 por cualquier otro reclamo, ya sea basado en el incumplimiento del contrato, negligencia o responsabilidad del Producto, no excederá el precio pagado por estos mismos. En ningún caso GRUPO 3P1 será responsable de ningún daño especial, incidental, consecuente o de otro tipo, incluyendo, pero no limitando, pérdida de beneficios, retraso de reclamos y reclamaciones de terceros, independientemente de su causa. GRUPO 3P1 no se hace responsable por el deterioro o daños causados por terceros a los Productos, materiales o herramientas consignados en Obra.\n\n22) PÓLIZAS Y RETENIDOS: Para los proyectos en los que GRUPO 3P1 asume el valor de la póliza no aceptará que le sean practicados retenidos por garantía. GRUPO 3P1 no aceptará en ningún caso retenidos por garantía que no hayan sido previamente pactados por las partes y estén claramente especificados en el contrato, de lo contrario, GRUPO 3P1 se reserva el derecho a facturar intereses por mora a la tasa máxima legal autorizada por el incumplimiento en los plazos pactados.\n\n23) CUMPLIMIENTO DE LAS LEYES: GRUPO 3P1 garantiza y certifica que cumple con todos los estatutos, normas, reglamentos y órdenes aplicables de la República de Colombia, entre ellos los relacionados con mano de obra, salarios, horas laborales y otras condiciones de contratación y empleo. En caso de ser requerido por la ley, el Cliente se compromete a desvincular y mantener indemne a GRUPO 3P1 y las Empresas del Grupo, de cualquier relación generada por pesquisa, acusación o investigación de toda clase por parte de entes gubernamentales, legales, privados o cualquier otro tipo; GRUPO 3P1 desconoce la actividad económica, comercial o proceder del Cliente, y no está vinculado a estos, actuando siempre desde el principio de buena fe consagrado en la Sentencia C-1194/08 de la Corte Constitucional.\n\n24) CONTRATOS CON EL ESTADO: Si los Productos se van a utilizar en el cumplimiento de un contrato con el estado u organismos gubernamentales, GRUPO 3P1 cumplirá con todos los requisitos obligatorios de dicho contrato que sean aplicables a GRUPO 3P1, siempre que esta haya recibido notificación por escrito de dichos requerimientos con tiempo suficiente para incorporar su impacto en la lista de precios y la entrega de dichos Productos. Además, GRUPO 3P1 podrá a su elección, adoptar las disposiciones de otras leyes o reglamentos estatales que sean aplicables a GRUPO 3P1, o dimitir de la oferta si considera que no cumple con los requisitos necesarios para el cumplimiento del mismo.\n\n25) RENUNCIA: Los derechos y recursos de GRUPO 3P1, como se establece en este acuerdo, serán adicionales a cualquier otro derecho y recursos previstos en la ley o la equidad, y el fracaso o retraso por parte de GRUPO 3P1 de ejercer cualquier derecho o recurso en virtud del presente, no operará como una renuncia general de los mismos.\n\n26) CESIÓN: El Cliente no podrá ceder ninguno de sus derechos u obligaciones sin el consentimiento por escrito de GRUPO 3P1.\n\n27) AVISOS: Todos los avisos y otras comunicaciones requeridas o permitidas que se indican a continuación deberán ser por escrito y serán efectivas cuando se entregan personalmente, transmitidas electrónicamente o enviadas por correo certificado con portes prepagados.\n\n28) DIVISIBILIDAD: En el caso de que una o varias previsiones del presente deban celebrarse como inaplicables en cualquier relación, éste documento se interpretará como si tales disposiciones inaplicables no hubiesen sido contenidas en el presente documento.\n\n29) LEY APLICABLE: La compra de los Productos deberá en todos los aspectos ser regida por las leyes de la República de Colombia, sin tener en cuenta sus conflictos de disposiciones legales. Si fuera necesario para cualquiera de las partes comenzar cualquier acción legal para hacer cumplir estos términos, la parte vencedora en dicha acción tendrá derecho a recuperar de la parte perdedora todos los honorarios razonables de abogados, costos y gastos incurridos en la acusación o la defensa de tales acciones y cualquier apelación.\n\n30) PROPIEDAD INTELECTUAL: Todos los productos, servicios, material, información, bienes y derechos que se encuentran plasmados en los documentos, correos electrónicos, página web e instalaciones de GRUPO 3P1 son protegidos por la propiedad intelectual, los derechos de autor o la propiedad industrial según corresponda, por lo cual los mismos solamente podrán ser utilizados para los fines mencionados en los términos de uso, y en consecuencia, no podrán ser utilizados por los usuarios con fines distintos a los previstos, en especial con fines de lucro, apropiación, distribución, reutilización, modificación, deformación, mutilación o utilizar dicho contenido con fines públicos, políticos, comerciales entre otros, sin contar previamente con la respectiva autorización expresa y escrita de GRUPO 3P1.\n\n31) ACUERDO COMPLETO: Estos Términos y Condiciones reemplazan todos los demás acuerdos, representaciones, garantías y compromisos de las partes con respecto al objeto del mismo y no se pueden modificar, excepto por un escrito firmado por un funcionario autorizado de GRUPO 3P1. Si el Cliente y GRUPO 3P1 han ejecutado un acuerdo primordial que cubre la venta de los Productos a los que se refiere el presente documento, los términos de dicho acuerdo primordial prevalecerán sobre los términos establecidos en éste documento sólo en la medida de cualquier conflicto.")
                            font.pixelSize: 16
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Rectangle {
                    id: boxAdvancedUser
                    x: 282
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"
                    ScrollView {
                        id: scrollViewAdvancedUser
                        x: 0
                        y: 0
                        width: 1064
                        height: 546
                        Text {
                            id: txtAdvancedUser
                            x: 16
                            y: 17
                            width: 1032
                            height: 511
                            color: "#f2f8f9"
                            text: qsTr("Activa el modo avanzado y toma el control total de tus máquinas, sácale el máximo partido a nuestro Ecosistema en todo tipo de situación, optimiza diversas máquinas con configuraciones específicas según el uso o aplicación. Estudia, trabaja, crea, disfruta, diseña, programa, vende, gestiona, automatiza, comprime, compila, despliega y mucho, MUCHO MÁS!...")
                            font.pixelSize: 16
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Rectangle {
                    id: boxIntermediateUser
                    x: 282
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"
                    ScrollView {
                        id: scrollViewIntermediateUser
                        x: 0
                        y: 0
                        width: 1064
                        height: 546
                        Text {
                            id: txtIntermediateUser
                            x: 16
                            y: 17
                            width: 1032
                            height: 511
                            color: "#f2f8f9"
                            text: qsTr("Guarda la configuración de tus máquinas en el Terminal ⌨️ por ejemplo, para largos periodos de inactividad, y recupérala fácil y rápido cuando la vuelvas a necesitar. Cambia la configuración de tus máquinas existentes, duplicalas y restaura Snapshots para volver a una versión anterior. Sincroniza los archivos en tus máquinas con tu almacenamiento local para que puedas usarlos en otros dispositivos, o recuperarlos si algo sale mal.")
                            font.pixelSize: 16
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Rectangle {
                    id: boxFirstSteps
                    x: 282
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"
                    ScrollView {
                        id: scrollViewFirstSteps
                        x: 0
                        y: 0
                        width: 1064
                        height: 546
                        Text {
                            id: txtFirstSteps
                            x: 16
                            y: 17
                            width: 1032
                            height: 511
                            color: "#f2f8f9"
                            text: qsTr("Crea una cuenta nueva, no necesitas saldo para comenzar a usar el servicio (Ads). Puedes crear una máquina a tu gusto o usar la que viene creada por defecto, es gratis y fácil de usar (Requiere Conexión a Internet).")
                            font.pixelSize: 16
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                Rectangle {
                    id: boxSliceDefinition
                    x: 283
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"

                    Text {
                        id: txtSliceDefinition
                        x: 25
                        y: 31
                        width: 839
                        height: 487
                        color: "#f2f8f9"
                        text: qsTr("Especificaciones Técnicas Porción Coffee Pie®:\n\nPWR: 1 Wh\nCPU: 1 Core\nRAM: 1 GB\nSSD: 8 GB\nNET: 8 Mbps\nHDD: 125 GB\nGPU: 125 MB\nRES: 3 MPX/s\nIA: 3 TOPS")
                        font.pixelSize: 30
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Rectangle {
                    id: boxAboutCoffeePie
                    x: 282
                    y: 102
                    width: 1064
                    height: 546
                    visible: false
                    color: "#323030"
                    ScrollView {
                        id: scrollViewAboutCoffeePie
                        x: 0
                        y: 0
                        width: 1064
                        height: 546
                        Text {
                            id: txtAboutCoffeePie
                            x: 16
                            y: 17
                            width: 1032
                            height: 511
                            visible: true
                            color: "#f2f8f9"
                            text: qsTr("Te imaginas poder aumentar el poder de cómputo y capacidad de tu equipo con un par de clicks y sin pagar de más?...\n​\n\nTe imaginas no tener que tirar a la basura tu equipo cada 2 ó 3 años porque ya está lento, obsoleto o se te dañó una tecla?...\n\n​\nTe imaginas poder cambiar los puertos de tu equipo sin tener que comprar uno nuevo cada que cambien tus necesidades?...\n​\n\nTe imaginas poder cotribuir al desarrollo social e industrial, sin afectar al medio ambiente y sin generar basura electrónica?...\n\n​\nCon Coffe Pie® ahora todo eso es posible!")
                            font.pixelSize: 22
                            wrapMode: Text.WordWrap
                        }
                    }
                }





            }

            Button {
                id: buttonSliceDefinition
                x: 237
                y: 279
                width: 281
                height: 66
                visible: true
                text: qsTr("")
                flat: true
                Text {
                    id: lblSliceDefinition
                    x: 8
                    y: 12
                    width: 275
                    height: 46
                    visible: true
                    color: "#f2f8f9"
                    text: qsTr("Definición de Porción")
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                }

                Connections {
                    target: buttonSliceDefinition
                    function onClicked() {
                        boxAboutCoffeePie.visible = false
                        boxSliceDefinition.visible = true
                        boxFirstSteps.visible = false
                        boxIntermediateUser.visible = false
                        boxAdvancedUser.visible = false
                        boxTermsAndConditions.visible = false
                        boxPrivacyPolicy.visible = false
                    }
                }
            }

            Button {
                id: buttonFirstSteps
                x: 237
                y: 351
                width: 281
                height: 66
                visible: true
                text: qsTr("")
                flat: true
                Text {
                    id: lblFirstSteps
                    x: 8
                    y: 12
                    width: 273
                    height: 46
                    visible: true
                    color: "#f2f8f9"
                    text: qsTr("Primeros Pasos")
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                }

                Connections {
                    target: buttonFirstSteps
                    function onClicked() {
                        boxAboutCoffeePie.visible = false
                        boxSliceDefinition.visible = false
                        boxFirstSteps.visible = true
                        boxIntermediateUser.visible = false
                        boxAdvancedUser.visible = false
                        boxTermsAndConditions.visible = false
                        boxPrivacyPolicy.visible = false
                    }
                }
            }

            Button {
                id: buttonIntermediateUser
                x: 237
                y: 423
                width: 281
                height: 66
                visible: true
                text: qsTr("")
                flat: true
                Text {
                    id: lblIntermediateUser
                    x: 8
                    y: 12
                    width: 273
                    height: 46
                    visible: true
                    color: "#f2f8f9"
                    text: qsTr("Usuario Intermedio")
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                }

                Connections {
                    target: buttonIntermediateUser
                    function onClicked() {
                        boxAboutCoffeePie.visible = false
                        boxSliceDefinition.visible = false
                        boxFirstSteps.visible = false
                        boxIntermediateUser.visible = true
                        boxAdvancedUser.visible = false
                        boxTermsAndConditions.visible = false
                        boxPrivacyPolicy.visible = false
                    }
                }
            }

            Button {
                id: buttonAdvancedUser
                x: 237
                y: 490
                width: 281
                height: 66
                visible: true
                text: qsTr("")
                flat: true
                Text {
                    id: lblAdvancedUser
                    x: 8
                    y: 12
                    width: 273
                    height: 46
                    visible: true
                    color: "#f2f8f9"
                    text: qsTr("Usuario Avanzado")
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                }

                Connections {
                    target: buttonAdvancedUser
                    function onClicked() {
                        boxAboutCoffeePie.visible = false
                        boxSliceDefinition.visible = false
                        boxFirstSteps.visible = false
                        boxIntermediateUser.visible = false
                        boxAdvancedUser.visible = true
                        boxTermsAndConditions.visible = false
                        boxPrivacyPolicy.visible = false
                    }
                }
            }

            Button {
                id: buttonTermsAndConditions
                x: 237
                y: 556
                width: 281
                height: 66
                visible: true
                text: qsTr("")
                flat: true
                Text {
                    id: lblTermsAndConditions
                    x: 8
                    y: 12
                    width: 273
                    height: 46
                    visible: true
                    color: "#f2f8f9"
                    text: qsTr("Términos y Condiciones")
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                }

                Connections {
                    target: buttonTermsAndConditions
                    function onClicked() {
                        boxAboutCoffeePie.visible = false
                        boxSliceDefinition.visible = false
                        boxFirstSteps.visible = false
                        boxIntermediateUser.visible = false
                        boxAdvancedUser.visible = false
                        boxTermsAndConditions.visible = true
                        boxPrivacyPolicy.visible = false
                    }
                }
            }

            Button {
                id: buttonPrivacyPolicy
                x: 237
                y: 628
                width: 281
                height: 66
                visible: true
                text: qsTr("")
                flat: true
                Text {
                    id: lblPrivacyPolicy
                    x: 8
                    y: 12
                    width: 273
                    height: 46
                    visible: true
                    color: "#f2f8f9"
                    text: qsTr("Política de Privacidad")
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                }

                Connections {
                    target: buttonPrivacyPolicy
                    function onClicked() {
                        boxAboutCoffeePie.visible = false
                        boxSliceDefinition.visible = false
                        boxFirstSteps.visible = false
                        boxIntermediateUser.visible = false
                        boxAdvancedUser.visible = false
                        boxTermsAndConditions.visible = false
                        boxPrivacyPolicy.visible = true
                    }
                }
            }
        }
    }

    MessageDialog {
        id: userCreatedDialog
        title: qsTr("Registro de usuario")
        text: ""
        visible: false
        onAccepted: visible = false
    }

    Connections {
        target: myMachine
        function onUserCreated(success, message) {
            userCreatedDialog.text = message
            userCreatedDialog.visible = true
        }
    }
}
