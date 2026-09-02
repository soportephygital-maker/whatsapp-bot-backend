def coppel_decision_tree() -> dict:
    human = {'comando': '0, asesor, humano, persona, soporte', 'respuesta': 'Voy a canalizarte con un integrante del equipo de soporte. Ticket: [NUMERO_TICKET]\nEstado: ABIERTO\nConservaré la información que ya me proporcionaste para que no tengas que repetirla.', 'siguiente': 'humano', 'accion': 'human_help'}
    menu = {
        'mensaje': 'Gracias. ¿En qué puedo ayudarte?\n1) Reportar un problema\n2) Vincular o desvincular un preciador\n3) Consultar un ticket\n4) Consultar una visita o servicio\n5) Guías y videos de apoyo\n6) Preguntas frecuentes\n7) Hablar con soporte\nTambién puedes escribir directamente lo que está sucediendo.',
        'opciones': [
            {'comando': '1, reportar, problema, falla', 'respuesta': '', 'siguiente': 'reportar'},
            {'comando': '2, vincular, desvincular, assign, unassign', 'respuesta': '', 'siguiente': 'vinculacion_menu'},
            {'comando': '3, ticket, reporte, estatus, status', 'respuesta': '', 'siguiente': 'consulta_ticket', 'accion': 'ticket_status'},
            {'comando': '4, visita, servicio', 'respuesta': 'Para consultar una visita o servicio necesito el número de ticket. Escríbelo a continuación.', 'siguiente': 'consulta_ticket', 'accion': 'ticket_status'},
            {'comando': '5, guia, guía, video, videos, guias, guías', 'respuesta': '', 'siguiente': 'guias'},
            {'comando': '6, preguntas, frecuentes, faq', 'respuesta': '', 'siguiente': 'faq'},
            {'comando': '7, asesor, humano, persona, soporte', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
        ],
    }
    return {
        'identificacion': {
            'aliases': ['Coppel'],
            'keywords': ['coppel', 'tienda coppel', 'departamento coppel'],
            'tags': ['coppel', 'preciadores', 'aims'],
        },
        'nodo_raiz': 'inicio',
        'respuesta_sin_sentido_1': 'No entendí bien tu respuesta. Puedes seleccionar una de las opciones disponibles o escribir nuevamente lo que sucede.',
        'respuesta_sin_sentido_2': 'Todavía no logro identificar correctamente tu solicitud. Escribe MENU para regresar al menú o ASESOR para hablar con una persona.',
        'nodos': {
            'inicio': {
                'mensaje': 'Bienvenido al canal de atención de Phygital para Coppel. Estoy aquí para ayudarte con dudas, solicitudes o problemas relacionados con los equipos de tu tienda. Para continuar, indícame tu nombre. Si lo deseas, también puedes escribir tu puesto. Ejemplo: Juan Pérez - Gerente.',
                'opciones': [
                    {'comando': 'menu, menú, inicio', 'respuesta': menu['mensaje'], 'siguiente': 'menu'},
                    {'comando': 'asesor, humano, persona, soporte', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                ],
                'tipo': 'router',
                'rutas': [{'palabras': [], 'coincidencia': 'contains', 'prioridad': 1, 'siguiente': 'menu', 'respuesta': menu['mensaje']}],
                'fallback': {'siguiente': 'menu', 'respuesta': menu['mensaje']},
            },
            'menu': menu,
            'reportar': {
                'mensaje': 'Claro. ¿Qué está sucediendo?\n1) Un preciador está apagado o en blanco\n2) El precio no cambia o está incorrecto\n3) Aparece un producto equivocado\n4) Varios preciadores tienen problemas\n5) Hay problema de señal o comunicación\n6) Un preciador está roto o golpeado\n7) Una base, soporte o accesorio está dañado\n8) AIMS muestra un error\n9) Tengo otro problema\n0) Hablar con una persona',
                'opciones': [
                    {'comando': '1, apagado, blanco, no prende, no enciende', 'respuesta': '', 'siguiente': 'apagado_dano'},
                    {'comando': '2, precio, precio incorrecto, no cambia, precio viejo', 'respuesta': '', 'siguiente': 'precio_tipo'},
                    {'comando': '3, producto equivocado, producto incorrecto', 'respuesta': '', 'siguiente': 'producto_equivocado'},
                    {'comando': '4, varios, muchos, varios preciadores', 'respuesta': '', 'siguiente': 'varios_cantidad'},
                    {'comando': '5, señal, senal, comunicacion, comunicación, offline', 'respuesta': '', 'siguiente': 'comunicacion'},
                    {'comando': '6, roto, golpeado, daño fisico, daño físico, pantalla rota', 'respuesta': '', 'siguiente': 'dano_fisico'},
                    {'comando': '7, base, soporte, accesorio, accesorio dañado', 'respuesta': '', 'siguiente': 'accesorio'},
                    {'comando': '8, aims, error aims, error', 'respuesta': '', 'siguiente': 'aims_error'},
                    {'comando': '9, otro, otro problema', 'respuesta': '', 'siguiente': 'otro_problema'},
                    human,
                ],
            },
            'apagado_dano': {
                'mensaje': 'Entendido. Vamos a hacer una revisión sencilla. Primero dime si el preciador tiene algún daño visible.\n1) No tiene golpes ni daños visibles\n2) Tiene un golpe, pantalla rota o daño físico\n3) No estoy seguro',
                'opciones': [
                    {'comando': '1, no, sin daño, sin dano', 'respuesta': 'Perfecto. Antes de generar un reporte vamos a intentar activarlo. Presiona el botón del preciador y revisa si la pantalla responde. Si tu modelo cuenta con Botón 1 y no responde, mantenlo presionado aproximadamente 3 segundos.', 'siguiente': 'apagado_prueba'},
                    {'comando': '2, golpe, roto, daño, dano', 'respuesta': '', 'siguiente': 'dano_fisico'},
                    {'comando': '3, no estoy seguro, no se, no sé', 'respuesta': 'Si puedes, envíame una fotografía del preciador completo. La fotografía se utilizará como evidencia del reporte.', 'siguiente': 'apagado_evidencia'},
                    human,
                ],
            },
            'apagado_prueba': {
                'mensaje': 'Después dime qué ocurrió:\n1) Ya encendió y funciona\n2) Sigue apagado o en blanco\n3) No sé cuál botón utilizar\n4) No pude hacerlo\n0) Hablar con soporte',
                'opciones': [
                    {'comando': '1, ya encendio, ya encendió, funciona, solucionado', 'respuesta': 'Perfecto. El preciador volvió a funcionar. Tu atención quedó registrada.\nTicket: [NUMERO_TICKET]\nEstado: CERRADO\nMotivo: Preciador apagado\nResultado: Solucionado', 'siguiente': 'cierre_resuelto', 'accion': 'ticket_close'},
                    {'comando': '2, sigue apagado, blanco, no funciona', 'respuesta': 'Entendido. El preciador continúa sin funcionar después de la revisión. No lo abras ni intentes cambiar la batería. Si puedes, envíame una fotografía del preciador completo como evidencia.', 'siguiente': 'apagado_evidencia'},
                    {'comando': '3, no se, no sé, boton, botón, 4, no pude', 'respuesta': 'No hay problema. Te comparto la guía de activación. Cuando termines dime si ya funciona, sigue apagado o no pudiste realizarlo.', 'siguiente': 'apagado_prueba'},
                    human,
                ],
            },
            'apagado_evidencia': {
                'mensaje': 'Gracias. La evidencia quedará asociada al reporte. Voy a registrar el caso para que soporte continúe con la revisión.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Preciador no enciende\nNuestro equipo continuará con la atención.',
                'opciones': [human],
            },
            'precio_tipo': {
                'mensaje': 'Entendido. ¿Qué está sucediendo con el precio?\n1) El precio no cambia\n2) El precio mostrado es incorrecto\n3) Aparece un precio anterior\n4) La información está incompleta\n5) No estoy seguro',
                'opciones': [
                    {'comando': '1, 2, 3, 4, 5, no cambia, incorrecto, anterior, incompleta, no estoy seguro', 'respuesta': '¿Cuántos preciadores presentan el problema?\n1) Solo uno\n2) De 2 a 5\n3) De 6 a 20\n4) Más de 20\n5) Una zona completa\n6) Varias áreas de la tienda', 'siguiente': 'precio_cantidad'},
                    human,
                ],
            },
            'precio_cantidad': {
                'mensaje': 'Indica la cantidad afectada.',
                'opciones': [
                    {'comando': '1, solo uno, uno', 'respuesta': 'Vamos a revisar el preciador en AIMS Manager. Abre AIMS Manager, selecciona la tienda correspondiente y entra a Search. Puedes buscar utilizando el código del producto, nombre del producto o código del preciador. Cuando lo encuentres, revisa el estado: Success, Processing, Timeout o no encontrado.', 'siguiente': 'aims_estado'},
                    {'comando': '2, 3, 4, 5, 6, varios, zona, areas, áreas, mas de 20, más de 20', 'respuesta': '', 'siguiente': 'varios_cantidad'},
                    human,
                ],
            },
            'aims_estado': {
                'mensaje': '¿Qué estado aparece?\n1) Success\n2) Processing\n3) Timeout\n4) No encuentro el preciador\n5) No puedo realizar esta revisión\n0) Hablar con soporte',
                'opciones': [
                    {'comando': '1, success', 'respuesta': 'El sistema indica que la información fue enviada correctamente. Ahora necesitamos comprobar que el preciador esté relacionado con el producto correcto. ¿El producto que aparece en AIMS corresponde al producto físico?\n1) Sí\n2) No\n3) No estoy seguro', 'siguiente': 'success_producto'},
                    {'comando': '2, processing, 3, timeout', 'respuesta': '', 'siguiente': 'refresh_nfc'},
                    {'comando': '4, no encuentro, no aparece', 'respuesta': 'El preciador no fue localizado. Si puedes, envíame una fotografía del identificador o una captura de AIMS. Voy a registrar el caso para soporte.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Preciador no reconocido en AIMS', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '5, no puedo', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'success_producto': {
                'mensaje': '¿El producto mostrado corresponde al producto físico?',
                'opciones': [
                    {'comando': '1, si, sí, correcto', 'respuesta': 'Si AIMS muestra Success y el producto es correcto, revisa nuevamente la pantalla. Si la información continúa incorrecta, registraremos el caso para soporte.', 'siguiente': 'verificar_resuelto'},
                    {'comando': '2, no, otro producto', 'respuesta': 'Entendido. Necesitamos corregir la vinculación. ¿Qué deseas hacer?\n1) Realizar la vinculación ahora\n2) Ver una guía o video\n3) Hablar con soporte', 'siguiente': 'vinculacion_menu'},
                    {'comando': '3, no estoy seguro', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'refresh_nfc': {
                'mensaje': 'La actualización todavía no se completó correctamente. Si tu teléfono y AIMS Manager tienen NFC habilitado, podemos intentar actualizar el preciador.\n1) Sí\n2) Ver video\n3) No tengo NFC\n4) Hablar con soporte',
                'opciones': [
                    {'comando': '1, si, sí', 'respuesta': 'Abre AIMS Manager, verifica que NFC esté activado, entra a Beeper, selecciona Refresh, acerca el teléfono al preciador y espera a que se complete la acción. ¿Qué ocurrió?\n1) Ya actualizó correctamente\n2) Sigue sin actualizar\n3) No pude realizarlo', 'siguiente': 'refresh_resultado'},
                    {'comando': '2, video', 'respuesta': 'Te comparto la guía de Refresh con NFC. Después vuelve y dime si actualizó correctamente.', 'siguiente': 'refresh_resultado'},
                    {'comando': '3, no tengo nfc, 4, soporte', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'refresh_resultado': {
                'mensaje': 'Indica el resultado del Refresh.',
                'opciones': [
                    {'comando': '1, actualizo, actualizó, funciona', 'respuesta': 'Perfecto. La actualización se realizó correctamente.\nTicket: [NUMERO_TICKET]\nEstado: CERRADO\nMotivo: Preciador no actualizaba\nResultado: Solucionado', 'siguiente': 'cierre_resuelto', 'accion': 'ticket_close'},
                    {'comando': '2, sigue sin actualizar, 3, no pude', 'respuesta': 'Entendido. La actualización continúa sin completarse. Si puedes, envíame una captura donde aparezca el estado o mensaje de AIMS.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Preciador no actualiza', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'vinculacion_menu': {
                'mensaje': '¿Qué deseas hacer?\n1) Vincular un preciador\n2) Desvincular un preciador\n0) Hablar con soporte',
                'opciones': [
                    {'comando': '1, vincular, assign', 'respuesta': 'Abre AIMS Manager y selecciona la tienda correcta. Selecciona Assign, escanea o escribe el código del producto, confirma el producto correcto y luego escanea o escribe el código del preciador. ¿Qué ocurrió?\n1) Assign Complete\n2) No encuentra el producto\n3) No reconoce el preciador\n4) Dice que ya está asignado\n5) Apareció otro error\n6) No pude realizarlo', 'siguiente': 'assign_resultado'},
                    {'comando': '2, desvincular, unassign', 'respuesta': 'Abre AIMS Manager, selecciona la tienda correspondiente, elige Unassign, escanea o escribe el código del preciador y confirma la operación. ¿Qué ocurrió?\n1) Unassign Complete\n2) Apareció un error\n3) No reconoce el preciador\n4) No pude realizarlo', 'siguiente': 'unassign_resultado'},
                    human,
                ],
            },
            'assign_resultado': {
                'mensaje': 'Indica el resultado de Assign.',
                'opciones': [
                    {'comando': '1, assign complete, completo', 'respuesta': 'Perfecto. El preciador quedó relacionado correctamente con el producto. Revisa ahora si muestra la información correcta.\n1) Sí, ya está correcto\n2) No, continúa incorrecto', 'siguiente': 'verificar_resuelto'},
                    {'comando': '2, no encuentra producto, producto no encontrado', 'respuesta': 'Verifica una vez más que el código capturado sea correcto. Si es correcto y el producto sigue sin aparecer, no sigas intentando crear o modificar el producto. Envíame una captura de AIMS.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Producto no disponible para vinculación', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '3, no reconoce preciador', 'respuesta': 'Escanea nuevamente el código, escríbelo manualmente o utiliza la cámara de AIMS Manager si tu dispositivo lo permite. Si sigue sin reconocerlo, envíame una foto del identificador o una captura.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Preciador no reconocido en AIMS', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '4, ya esta asignado, ya está asignado', 'respuesta': 'AIMS indica que el preciador ya tiene una asignación. ¿El producto mostrado corresponde al producto correcto?\n1) Sí\n2) No, está relacionado con otro producto\n3) AIMS indica que pertenece a otra tienda\n4) No estoy seguro', 'siguiente': 'ya_asignado'},
                    {'comando': '5, otro error, 6, no pude', 'respuesta': '', 'siguiente': 'aims_error'},
                    human,
                ],
            },
            'ya_asignado': {
                'mensaje': 'Confirma la situación de la asignación.',
                'opciones': [
                    {'comando': '1, si, sí, correcto', 'respuesta': 'La asignación ya es correcta. Si la pantalla también muestra la información correcta, registraré la atención como solucionada.', 'siguiente': 'verificar_resuelto'},
                    {'comando': '2, otro producto', 'respuesta': 'Primero vamos a desvincular el preciador y después podremos relacionarlo con el producto correcto.', 'siguiente': 'vinculacion_menu'},
                    {'comando': '3, otra tienda', 'respuesta': 'AIMS indica que el preciador está relacionado con otra tienda. ¿Fue trasladado intencionalmente?\n1) Sí\n2) No\n3) No estoy seguro', 'siguiente': 'otra_tienda'},
                    {'comando': '4, no estoy seguro', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'otra_tienda': {
                'mensaje': '¿El preciador fue trasladado intencionalmente de otra tienda?',
                'opciones': [
                    {'comando': '1, si, sí', 'respuesta': 'Si tienes autorización para trasladarlo, confirma la reasignación en AIMS. Si la reasignación fue exitosa escribe LISTO.', 'siguiente': 'reasignacion_resultado'},
                    {'comando': '2, no, 3, no estoy seguro', 'respuesta': 'No continúes con la reasignación. Voy a registrar el caso para evitar modificar por error la información de otra tienda.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Conflicto de asignación entre tiendas', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'reasignacion_resultado': {
                'mensaje': 'Indica si la reasignación fue exitosa o apareció un error.',
                'opciones': [
                    {'comando': 'listo, exitosa, correcto', 'respuesta': 'Perfecto. La reasignación quedó completada.\nTicket: [NUMERO_TICKET]\nEstado: CERRADO\nMotivo: Reasignación de preciador\nResultado: Solucionado', 'siguiente': 'cierre_resuelto', 'accion': 'ticket_close'},
                    {'comando': 'error, fallo, no pude', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'unassign_resultado': {
                'mensaje': 'Indica el resultado de Unassign.',
                'opciones': [
                    {'comando': '1, unassign complete, completo', 'respuesta': 'Perfecto. El preciador quedó desvinculado. ¿Qué deseas hacer ahora?\n1) Vincularlo con otro producto\n2) Ya terminé', 'siguiente': 'unassign_despues'},
                    {'comando': '2, error, 3, no reconoce, 4, no pude', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'unassign_despues': {
                'mensaje': '¿Qué deseas hacer ahora?',
                'opciones': [
                    {'comando': '1, vincular', 'respuesta': '', 'siguiente': 'vinculacion_menu'},
                    {'comando': '2, termine, terminé, listo', 'respuesta': 'Perfecto. Voy a registrar la atención como solucionada.\nTicket: [NUMERO_TICKET]\nEstado: CERRADO\nMotivo: Desvinculación de preciador\nResultado: Solucionado', 'siguiente': 'cierre_resuelto', 'accion': 'ticket_close'},
                    human,
                ],
            },
            'producto_equivocado': {
                'mensaje': 'Vamos a comprobar la relación del producto en AIMS Manager. Busca el preciador por su código y revisa el producto relacionado. ¿Qué observas?\n1) Está relacionado con otro producto\n2) El producto es correcto pero la pantalla muestra información incorrecta\n3) No encuentro el preciador\n4) No puedo realizar la revisión',
                'opciones': [
                    {'comando': '1, otro producto', 'respuesta': 'Primero utiliza Unassign y después vuelve a realizar Assign con el producto correcto.', 'siguiente': 'vinculacion_menu'},
                    {'comando': '2, producto correcto, informacion incorrecta, información incorrecta', 'respuesta': '', 'siguiente': 'aims_estado'},
                    {'comando': '3, no encuentro, 4, no puedo', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'aims_error': {
                'mensaje': 'Entendido. ¿Qué problema tienes en AIMS?\n1) No puedo iniciar sesión\n2) No aparece mi tienda\n3) No encuentra un producto\n4) No reconoce un preciador\n5) No permite vincular\n6) No permite desvincular\n7) Aparece un mensaje de error\n8) No tengo permisos para realizar la operación\n0) Hablar con soporte',
                'opciones': [
                    {'comando': '1, login, iniciar sesion, iniciar sesión', 'respuesta': 'Verifica que estés utilizando las credenciales asignadas para AIMS Manager. Si son correctas y el acceso continúa fallando, envíame una captura del mensaje. No realices cambios en la configuración del servidor.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Acceso a AIMS Manager', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '2, no aparece tienda', 'respuesta': 'En AIMS Manager solo aparecen las tiendas asignadas al usuario. Busca nuevamente por nombre o código. Si no aparece, registraré el caso para validar la asignación y permisos.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Tienda no disponible en AIMS', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '3, producto', 'respuesta': 'Si el código es correcto y el producto sigue sin aparecer, no sigas intentando crear o modificarlo. Envíame una captura.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Producto no disponible para vinculación', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '4, preciador', 'respuesta': 'Vuelve a escanear o escribir el código. Si sigue sin reconocerlo, envíame una foto del identificador o captura de AIMS.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Preciador no reconocido en AIMS', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '5, vincular, 6, desvincular, 7, mensaje de error, error', 'respuesta': 'Si puedes, envíame una captura de pantalla del mensaje. La imagen se utilizará como evidencia.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Error en AIMS Manager', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '8, permisos, sin permisos', 'respuesta': 'La operación requiere permisos adicionales. No es necesario que intentes modificar la configuración.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Permisos de usuario', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'dano_fisico': {
                'mensaje': 'Como existe daño físico, no intentes abrir, reparar o desarmar el preciador. Envíame una fotografía completa del preciador y otra donde se vea el daño. Indica si se cayó, recibió un golpe, se dañó durante el uso normal, ya estaba dañado o no saben cómo ocurrió.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Daño físico en preciador',
                'opciones': [human],
            },
            'bateria_baja': {
                'mensaje': 'AIMS está indicando batería baja. No abras el preciador ni intentes cambiar la batería; debe hacerlo personal autorizado.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Batería baja en preciador',
                'opciones': [human],
            },
            'varios_cantidad': {
                'mensaje': 'Aproximadamente, ¿cuántos preciadores tienen el problema?\n1) De 2 a 5\n2) De 6 a 20\n3) Más de 20\n4) Una zona completa\n5) Varias zonas\n6) Casi toda la tienda',
                'opciones': [
                    {'comando': '1, 2, 3, 4, 5, 6, varios, zona, tienda', 'respuesta': '¿Qué ocurre con ellos?\n1) Están apagados\n2) No cambian los precios\n3) Muestran información incorrecta\n4) Aparecen como Offline\n5) Tienen diferentes problemas', 'siguiente': 'varios_tipo'},
                    human,
                ],
            },
            'varios_tipo': {
                'mensaje': 'Si tienes acceso a AIMS Manager entra a Overview, revisa Warning Status y Gateway Status. ¿Qué observas?\n1) Aparecen varios Offline\n2) Aparece Bad Signal\n3) Hay un equipo de comunicación Offline\n4) Todo aparece normal\n5) No tengo acceso',
                'opciones': [
                    {'comando': '1, offline', 'respuesta': 'No es necesario reiniciar cada preciador. Si puedes, envíame una captura de AIMS donde aparezcan los equipos afectados.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Varios preciadores Offline', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '2, bad signal, señal debil, señal débil', 'respuesta': 'No modifiques configuraciones de red ni desconectes equipos. Envíame una captura del mensaje como evidencia.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Señal débil en preciadores', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '3, equipo offline, 4, normal, 5, no tengo acceso', 'respuesta': '', 'siguiente': 'comunicacion'},
                    human,
                ],
            },
            'comunicacion': {
                'mensaje': 'No necesitas saber el nombre técnico del equipo. ¿Qué observas en la caja, receptor o equipo de comunicación?\n1) No tiene ninguna luz encendida\n2) Tiene luces, pero los preciadores no actualizan\n3) Tiene alguna luz roja o de alerta\n4) El equipo está físicamente dañado\n5) No estoy seguro',
                'opciones': [
                    {'comando': '1, 2, 3, 4, 5, sin luces, roja, alerta, dañado, danado', 'respuesta': 'Si puedes, envíame una fotografía del equipo. No desconectes cables ni modifiques la conexión de red.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Problema de comunicación en tienda', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'accesorio': {
                'mensaje': 'Entendido. ¿Qué ocurrió?\n1) La base se desprendió\n2) La base está rota\n3) El soporte está flojo\n4) Falta una pieza\n5) El preciador se cayó por el soporte\n6) Hay otra pieza dañada',
                'opciones': [
                    {'comando': '1, 2, 3, 4, 5, 6, base, soporte, pieza', 'respuesta': 'No intentes repararlo de forma improvisada. Envíame una fotografía donde se vea la pieza dañada y el lugar donde estaba instalada.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Accesorio o soporte dañado\n¿La pieza puede caer, tiene cables expuestos o representa algún riesgo? Responde SI o NO.', 'siguiente': 'accesorio_riesgo'},
                    human,
                ],
            },
            'accesorio_riesgo': {
                'mensaje': '¿La pieza representa algún riesgo para clientes o personal?',
                'opciones': [
                    {'comando': 'si, sí, riesgo', 'respuesta': 'Por seguridad, no manipules la pieza y evita que clientes o personal permanezcan directamente debajo o junto al área afectada, si es posible hacerlo de forma segura.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO\nMotivo: Instalación con riesgo', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': 'no, sin riesgo', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'otro_problema': {
                'mensaje': 'Cuéntame brevemente qué sucede. No necesitas utilizar palabras técnicas. Ejemplos: “La pantallita no prende”, “El precio sigue viejo”, “La cajita que da señal está apagada”, “No puedo relacionar el producto”.',
                'opciones': [
                    {'comando': 'apagado, no prende', 'respuesta': '', 'siguiente': 'apagado_dano'},
                    {'comando': 'precio, precio viejo', 'respuesta': '', 'siguiente': 'precio_tipo'},
                    {'comando': 'vincular, relacionar, assign', 'respuesta': '', 'siguiente': 'vinculacion_menu'},
                    {'comando': 'varios, muchos', 'respuesta': '', 'siguiente': 'varios_cantidad'},
                    {'comando': 'señal, senal, cajita, comunicacion, comunicación', 'respuesta': '', 'siguiente': 'comunicacion'},
                    {'comando': 'roto, golpeado, daño, dano', 'respuesta': '', 'siguiente': 'dano_fisico'},
                    human,
                ],
                'fallback': {'siguiente': 'humano', 'respuesta': 'Todavía no logro identificar correctamente tu solicitud. Para evitar hacerte repetir más información, voy a canalizarte con soporte.\nTicket: [NUMERO_TICKET]\nEstado: ABIERTO', 'accion': 'human_help'},
            },
            'guias': {
                'mensaje': '¿Qué guía quieres consultar?\n1) Activar un preciador\n2) Vincular un preciador\n3) Desvincular un preciador\n4) Precio que no actualiza\n5) Uso de AIMS Manager\n6) Bases y soportes\n7) Limpieza y cuidados\n8) Otra guía\n0) Regresar al menú',
                'opciones': [
                    {'comando': '1, activar', 'respuesta': 'Guía: Activar un preciador. Presiona el botón del preciador y, si tu modelo cuenta con Botón 1 y no responde, mantenlo presionado aproximadamente 3 segundos.', 'siguiente': 'verificar_resuelto'},
                    {'comando': '2, vincular', 'respuesta': '', 'siguiente': 'vinculacion_menu'},
                    {'comando': '3, desvincular', 'respuesta': '', 'siguiente': 'vinculacion_menu'},
                    {'comando': '4, precio', 'respuesta': '', 'siguiente': 'precio_tipo'},
                    {'comando': '5, aims', 'respuesta': '', 'siguiente': 'aims_error'},
                    {'comando': '6, bases, soportes', 'respuesta': '', 'siguiente': 'accesorio'},
                    {'comando': '7, limpieza', 'respuesta': 'Para limpiar el preciador utiliza un paño suave o de microfibra. Si es necesario usa una pequeña cantidad de limpiador suave sin alcohol, sin presionar ni golpear la pantalla. Deja secar el equipo y evita productos abrasivos.', 'siguiente': 'verificar_resuelto'},
                    {'comando': '8, otra', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '0, menu, menú', 'respuesta': menu['mensaje'], 'siguiente': 'menu'},
                    human,
                ],
            },
            'faq': {
                'mensaje': '¿Qué deseas consultar?\n1) Cómo identificar el código de un preciador\n2) Cómo limpiar un preciador\n3) Qué hacer si un preciador está apagado\n4) Qué hacer si un preciador está roto\n5) Qué hacer si aparece batería baja\n6) Cómo vincular o desvincular\n7) Otra pregunta\n0) Regresar al menú',
                'opciones': [
                    {'comando': '1, codigo, código', 'respuesta': 'Puedes localizar el código del preciador en la etiqueta o identificador del equipo. En AIMS Manager también puedes escanearlo, escribirlo manualmente o usar la cámara cuando la función esté disponible.', 'siguiente': 'verificar_resuelto'},
                    {'comando': '2, limpiar, limpieza', 'respuesta': 'Usa un paño suave o de microfibra y, si es necesario, una pequeña cantidad de limpiador suave sin alcohol. Evita abrasivos.', 'siguiente': 'verificar_resuelto'},
                    {'comando': '3, apagado', 'respuesta': '', 'siguiente': 'apagado_dano'},
                    {'comando': '4, roto', 'respuesta': '', 'siguiente': 'dano_fisico'},
                    {'comando': '5, bateria, batería', 'respuesta': '', 'siguiente': 'bateria_baja'},
                    {'comando': '6, vincular, desvincular', 'respuesta': '', 'siguiente': 'vinculacion_menu'},
                    {'comando': '7, otra', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': '0, menu, menú', 'respuesta': menu['mensaje'], 'siguiente': 'menu'},
                    human,
                ],
            },
            'verificar_resuelto': {
                'mensaje': '¿Se resolvió tu consulta o problema?\n1) Sí, quedó resuelto\n2) No, necesito continuar\n3) Hablar con soporte',
                'opciones': [
                    {'comando': '1, si, sí, resuelto, solucionado', 'respuesta': 'Perfecto. Voy a registrar esta atención como solucionada.\nTicket: [NUMERO_TICKET]\nEstado: CERRADO\nResultado: Solucionado', 'siguiente': 'cierre_resuelto', 'accion': 'ticket_close'},
                    {'comando': '2, no, continuar', 'respuesta': menu['mensaje'], 'siguiente': 'menu'},
                    {'comando': '3, soporte', 'respuesta': human['respuesta'], 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'consulta_ticket': {
                'mensaje': 'Claro. Voy a consultar el ticket asociado a esta conversación.',
                'opciones': [
                    {'comando': 'menu, menú, regresar', 'respuesta': menu['mensaje'], 'siguiente': 'menu'},
                    human,
                ],
            },
            'cierre_resuelto': {
                'mensaje': '¿Necesitas ayuda con algo más?\n1) Sí, tengo otra solicitud\n2) No, finalizar',
                'opciones': [
                    {'comando': '1, si, sí, otra, otra solicitud', 'respuesta': menu['mensaje'], 'siguiente': 'menu'},
                    {'comando': '2, no, finalizar, salir', 'respuesta': 'Gracias por comunicarte con Phygital. Tu atención ha finalizado. Si necesitas ayuda nuevamente, puedes escribirnos por este mismo medio. Que tengas un excelente día.', 'siguiente': 'fin'},
                ],
            },
            'fin': {'mensaje': 'Atención finalizada.', 'opciones': [{'comando': 'inicio, menu, menú', 'respuesta': menu['mensaje'], 'siguiente': 'menu'}]},
            'humano': {'mensaje': '', 'opciones': []},
        },
    }
