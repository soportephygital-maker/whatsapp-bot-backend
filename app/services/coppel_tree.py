def coppel_decision_tree() -> dict:
    human = {'comando': 'humano, persona, soporte humano, asesor', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'}
    return {
        'identificacion': {
            'aliases': ['Coppel'],
            'keywords': ['coppel', 'tienda coppel', 'departamento coppel'],
            'tags': ['coppel'],
        },
        'nodo_raiz': 'inicio',
        'respuesta_sin_sentido_1': 'No logré identificar la opción. Indícame si necesitas apoyo con un accesorio o con una etiqueta.',
        'respuesta_sin_sentido_2': 'Sigo sin identificar el problema. Escribe accesorio, etiqueta o humano para solicitar atención de una persona.',
        'nodos': {
            'inicio': {
                'mensaje': 'Hola, bienvenido a soporte Coppel. Con gusto te ayudo. ¿El problema es con un accesorio o con una etiqueta?',
                'opciones': [
                    {'comando': '1, accesorio, accesorios', 'respuesta': '¿El accesorio se rompió o no se adhiere correctamente a la superficie?', 'siguiente': 'accesorio_tipo'},
                    {'comando': '2, etiqueta, etiquetas', 'respuesta': '¿Qué problema presenta la etiqueta?\n1) Contenido incorrecto\n2) Está dañada\n3) No muestra nada', 'siguiente': 'etiqueta_tipo'},
                    human,
                ],
            },
            'accesorio_tipo': {
                'mensaje': '¿El accesorio se rompió o no se adhiere a la superficie?',
                'opciones': [
                    {'comando': 'rompio, rompió, roto, quebrado, dañado, danado', 'respuesta': 'Voy a levantar el reporte para atención humana. Ten a la mano el departamento, la tienda y una foto del accesorio dañado.', 'siguiente': 'humano', 'accion': 'human_help'},
                    {'comando': 'no se adhiere, no pega, se despega, no se pega, no adhiere', 'respuesta': '¿El accesorio utiliza ventosa o imán?', 'siguiente': 'accesorio_fijacion'},
                    human,
                ],
            },
            'accesorio_fijacion': {
                'mensaje': '¿El accesorio utiliza ventosa o imán?',
                'opciones': [
                    {'comando': 'ventosa, ventosas', 'respuesta': 'Limpia la superficie y también la ventosa. Después humedece ligeramente la superficie con un trapo apenas húmedo y vuelve a colocar la ventosa. Dime si ya quedó bien adherida.', 'siguiente': 'ventosa_verificar'},
                    {'comando': 'iman, imán, magnetico, magnético', 'respuesta': 'Verifica que la superficie sea metálica, que el accesorio no esté cargando más peso que el de la etiqueta, que no falte ningún imán y que tanto los imanes como la superficie estén limpios. Después vuelve a colocarlo y dime si ya queda fijo.', 'siguiente': 'iman_verificar'},
                    human,
                ],
            },
            'ventosa_verificar': {
                'mensaje': 'Después de limpiar y humedecer ligeramente la superficie, ¿la ventosa ya se adhiere correctamente?',
                'opciones': [
                    {'comando': 'si, sí, ya, funciona, quedo, quedó, solucionado', 'respuesta': 'Perfecto. El accesorio quedó adherido correctamente. Si necesitas revisar otro caso, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue igual, no pega, no se adhiere, se despega', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'iman_verificar': {
                'mensaje': 'Después de verificar superficie metálica, peso, imanes y limpieza, ¿el accesorio ya queda fijo?',
                'opciones': [
                    {'comando': 'si, sí, ya, funciona, quedo, quedó, solucionado', 'respuesta': 'Perfecto. El accesorio quedó colocado correctamente. Si necesitas revisar otro caso, escribe inicio.', 'siguiente': 'final_resuelto'},
                    {'comando': 'no, sigue igual, se cae, no pega, no queda fijo', 'respuesta': '', 'siguiente': 'humano', 'accion': 'human_help'},
                    human,
                ],
            },
            'etiqueta_tipo': {
                'mensaje': '¿La etiqueta tiene contenido incorrecto, está dañada o no muestra nada?',
                'opciones': [
                    {'comando': '1, mal contenido, contenido incorrecto, informacion incorrecta, precio incorrecto, dato incorrecto', 'respuesta': 'Para levantar el reporte indícame: departamento, tienda, producto afectado, una foto de la etiqueta y una breve descripción de qué información aparece incorrecta. Después canalizaré el caso con atención humana.', 'siguiente': 'etiqueta_datos'},
                    {'comando': '2, dañada, danada, rota, quebrada, golpeada', 'respuesta': 'Para levantar el reporte indícame: departamento, tienda, producto afectado, una foto de la etiqueta y una breve descripción del daño. Después canalizaré el caso con atención humana.', 'siguiente': 'etiqueta_datos'},
                    {'comando': '3, no muestra nada, en blanco, apagada, sin informacion, sin información, pantalla negra', 'respuesta': 'Para levantar el reporte indícame: departamento, tienda, producto afectado, una foto de la etiqueta y confirma que no muestra información. Después canalizaré el caso con atención humana.', 'siguiente': 'etiqueta_datos'},
                    human,
                ],
            },
            'etiqueta_datos': {
                'mensaje': 'Envíame los datos solicitados y la foto. En cuanto los compartas, el caso será canalizado con soporte humano.',
                'tipo': 'router',
                'rutas': [
                    {'palabras': ['foto', 'adjunto', 'enviado', 'departamento', 'tienda', 'producto'], 'coincidencia': 'contains', 'prioridad': 10, 'siguiente': 'humano', 'respuesta': '', 'accion': 'human_help'},
                ],
                'fallback': {'siguiente': 'humano', 'respuesta': '', 'accion': 'human_help'},
            },
            'final_resuelto': {
                'mensaje': '¿Necesitas revisar otro problema? Escribe inicio para volver al menú o humano para solicitar atención de una persona.',
                'opciones': [
                    {'comando': 'inicio, menu, menú, otro, otro problema', 'respuesta': 'Claro. ¿El problema es con un accesorio o con una etiqueta?', 'siguiente': 'inicio'},
                    human,
                ],
            },
            'humano': {'mensaje': '', 'opciones': []},
        },
    }
