def iqos_decision_tree() -> dict:
    human = {'comando': 'humano, persona, soporte humano, asesor', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'}
    return {
        'identificacion': {
            'aliases': ['IQOS', 'Seven CCK', 'SEVEN-CCK'],
            'keywords': ['iqos', 'corner iqos', 'isla iqos'],
            'tags': ['iqos'],
        },
        'nodo_raiz': 'inicio',
        'respuesta_sin_sentido_1': 'No logré identificar la opción. Puedes indicarme si se trata de un Corner o una Isla y qué equipo presenta el problema: pantalla, tableta, audio o sensores/interacciones.',
        'respuesta_sin_sentido_2': 'Sigo sin identificar el problema. Escribe Corner o Isla y después pantalla, tableta, audio o sensores. Si necesitas atención de una persona escribe humano.',
        'nodos': {
            'inicio': {
                'mensaje': 'Hola, bienvenido a soporte IQOS. Con gusto te ayudo. Para comenzar, indícame si el problema se presenta en un Corner o en una Isla.',
                'opciones': [
                    {'comando': 'corner, corners', 'respuesta': 'Perfecto, revisemos el Corner. ¿Con qué necesitas apoyo?\n1) Pantalla\n2) Tableta\n3) Audio\n4) Sensores / interacciones', 'siguiente': 'corner_equipo'},
                    {'comando': 'isla, islas', 'respuesta': 'Perfecto, revisemos la Isla. ¿Con qué necesitas apoyo?\n1) Pantalla\n2) Tableta\n3) Audio\n4) Sensores / interacciones', 'siguiente': 'isla_equipo'},
                    human,
                ],
            },
            'corner_equipo': {
                'mensaje': '¿Qué equipo presenta el problema? 1) Pantalla 2) Tableta 3) Audio 4) Sensores / interacciones.',
                'opciones': [
                    {'comando': '1, pantalla, pantallas', 'respuesta': 'Vamos a revisar la pantalla. ¿La pantalla está prendida o está apagada?', 'siguiente': 'pantalla_estado'},
                    {'comando': '2, tableta, tablet, tabletas', 'respuesta': 'Vamos a revisar la tableta. ¿El problema es de sonido/volumen o de contenido incorrecto?', 'siguiente': 'tableta_tipo'},
                    {'comando': '3, audio, sonido', 'respuesta': 'Vamos a revisar el audio. ¿El problema es que el volumen está demasiado fuerte?', 'siguiente': 'audio_fuerte'},
                    {'comando': '4, sensor, sensores, interaccion, interacciones', 'respuesta': 'Vamos a revisar los sensores o interacciones. ¿No funcionan o están mostrando contenidos cruzados/incorrectos?', 'siguiente': 'sensores_tipo'},
                    human,
                ],
            },
            'isla_equipo': {
                'mensaje': '¿Qué equipo presenta el problema? 1) Pantalla 2) Tableta 3) Audio 4) Sensores / interacciones.',
                'opciones': [
                    {'comando': '1, pantalla, pantallas', 'respuesta': 'Vamos a revisar la pantalla. ¿La pantalla está prendida o está apagada?', 'siguiente': 'pantalla_estado'},
                    {'comando': '2, tableta, tablet, tabletas', 'respuesta': 'Vamos a revisar la tableta. ¿El problema es de sonido/volumen o de contenido incorrecto?', 'siguiente': 'tableta_tipo'},
                    {'comando': '3, audio, sonido', 'respuesta': 'Vamos a revisar el audio. ¿El problema es que el volumen está demasiado fuerte?', 'siguiente': 'audio_fuerte'},
                    {'comando': '4, sensor, sensores, interaccion, interacciones', 'respuesta': 'Vamos a revisar los sensores o interacciones. ¿No funcionan o están mostrando contenidos cruzados/incorrectos?', 'siguiente': 'sensores_tipo'},
                    human,
                ],
            },
            'pantalla_estado': {
                'mensaje': '¿La pantalla está prendida o apagada?',
                'opciones': [
                    {'comando': 'apagada, no prende, no enciende, sin energia, negra', 'respuesta': 'Desconecta la pantalla de la corriente, espera unos 10 segundos y vuelve a conectarla. Después dime si ya encendió.', 'siguiente': 'pantalla_reconexion'},
                    {'comando': 'prendida, encendida, si prende, si enciende', 'respuesta': '¿La información que muestra la pantalla es correcta o presenta algún problema de contenido/imagen?', 'siguiente': 'pantalla_prendida'},
                    human,
                ],
            },
            'pantalla_reconexion': {
                'mensaje': 'Después de desconectarla y volverla a conectar, ¿la pantalla ya encendió?',
                'opciones': [
                    {'comando': 'si, sí, ya, encendio, prendio, funciona', 'respuesta': 'Excelente. La pantalla volvió a encender. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue apagada, no encendio, no prendio', 'respuesta': 'Revisa si la pantalla tiene un apagador o interruptor visible y confirma que se encuentre encendido. Después dime si la pantalla ya prendió.', 'siguiente': 'pantalla_interruptor'},
                    human,
                ],
            },
            'pantalla_interruptor': {
                'mensaje': 'Después de revisar el interruptor, ¿la pantalla ya encendió?',
                'opciones': [
                    {'comando': 'si, sí, ya, funciona, encendio, prendio', 'respuesta': 'Perfecto. La pantalla ya está funcionando. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue igual, sigue apagada, no funciona', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'pantalla_prendida': {
                'mensaje': '¿La información mostrada es correcta?',
                'opciones': [
                    {'comando': 'si, sí, correcta, todo bien', 'respuesta': 'Perfecto. La pantalla está encendida y mostrando la información correcta. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, incorrecta, contenido incorrecto, falla, problema, imagen incorrecta', 'respuesta': 'Reinicia la pantalla. Cuando vuelva a encender, revisa nuevamente el contenido y dime si el problema continúa.', 'siguiente': 'pantalla_reinicio'},
                    human,
                ],
            },
            'pantalla_reinicio': {
                'mensaje': 'Después de reiniciar la pantalla, ¿el contenido ya se muestra correctamente?',
                'opciones': [
                    {'comando': 'si, sí, correcto, ya funciona, solucionado', 'respuesta': 'Excelente. El problema quedó resuelto. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue igual, incorrecto, sigue mal', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'tableta_tipo': {
                'mensaje': '¿El problema de la tableta es sonido/volumen o contenido incorrecto?',
                'opciones': [
                    {'comando': 'sonido, volumen, fuerte, audio', 'respuesta': 'Si la tableta tiene volumen alto, ayúdanos bajando el volumen desde sus controles. Después confirma si el nivel de audio quedó adecuado.', 'siguiente': 'tableta_volumen'},
                    {'comando': 'contenido, contenido incorrecto, informacion incorrecta, imagen incorrecta', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'tableta_volumen': {
                'mensaje': '¿El volumen de la tableta quedó en un nivel adecuado?',
                'opciones': [
                    {'comando': 'si, sí, adecuado, listo, solucionado', 'respuesta': 'Perfecto. El volumen quedó ajustado. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, no puedo, sigue fuerte, no baja', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'audio_fuerte': {
                'mensaje': '¿El problema es que el audio está demasiado fuerte?',
                'opciones': [
                    {'comando': 'si, sí, fuerte, muy fuerte, volumen alto', 'respuesta': '¿Cuentas con un control de volumen visible o disponible para ese audio?', 'siguiente': 'audio_control'},
                    {'comando': 'no, otro problema, no se escucha, sin audio', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'audio_control': {
                'mensaje': '¿Cuentas con un control para ajustar el volumen?',
                'opciones': [
                    {'comando': 'si, sí, tengo control, hay control', 'respuesta': 'Ayúdanos bajando el volumen con el control hasta un nivel adecuado. Después confirma si quedó solucionado.', 'siguiente': 'audio_verificar'},
                    {'comando': 'no, no hay control, sin control', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'audio_verificar': {
                'mensaje': '¿El nivel de audio quedó adecuado?',
                'opciones': [
                    {'comando': 'si, sí, listo, adecuado, solucionado', 'respuesta': 'Perfecto. El audio quedó ajustado. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue fuerte, no cambia, no funciona', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'sensores_tipo': {
                'mensaje': '¿Los sensores/interacciones no funcionan o presentan contenidos cruzados?',
                'opciones': [
                    {'comando': 'no funciona, no funcionan, no trabaja, no trabajan, sin interaccion, sensor no funciona', 'respuesta': 'Reinicia el código o módulo de la interacción y espera a que vuelva a cargar. Después prueba nuevamente la interacción y dime si ya funciona.', 'siguiente': 'sensores_reinicio'},
                    {'comando': 'contenido cruzado, contenidos cruzados, contenido incorrecto, cruzados, equivocado', 'respuesta': 'Por favor toma un video corto donde se vea la interacción y el contenido incorrecto o cruzado. Cuando lo tengas, envíalo por este chat para canalizar el caso con soporte.', 'siguiente': 'sensores_video'},
                    human,
                ],
            },
            'sensores_reinicio': {
                'mensaje': 'Después de reiniciar el código o módulo, ¿la interacción ya funciona?',
                'opciones': [
                    {'comando': 'si, sí, funciona, ya trabaja, solucionado', 'respuesta': 'Excelente. La interacción volvió a funcionar. Si necesitas revisar otro equipo, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue igual, no funciona, no trabaja', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                ],
            },
            'sensores_video': {
                'mensaje': 'Envíame el video del contenido cruzado para canalizarlo con soporte.',
                'tipo': 'router',
                'rutas': [
                    {'palabras': ['video', 'enviado', 'listo', 'adjunto'], 'coincidencia': 'contains', 'prioridad': 10, 'siguiente': 'humano', 'respuesta': '', 'accion': 'human_help'},
                ],
                'fallback': {'siguiente': 'humano', 'respuesta': '', 'accion': 'human_help'},
            },
            'final_resuelto': {
                'mensaje': '¿Necesitas revisar otro equipo? Escribe inicio para regresar al menú o humano si necesitas apoyo de una persona.',
                'opciones': [
                    {'comando': 'inicio, menu, menú, otro, otro equipo', 'respuesta': 'Claro. Indícame si el problema se presenta en un Corner o en una Isla.', 'siguiente': 'inicio'},
                    human,
                ],
            },
            'humano': {
                'mensaje': '',
                'opciones': [],
            },
        },
    }
