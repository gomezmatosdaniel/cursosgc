# CursosGC

Aplicación web de ejemplo para una plataforma de cursos tipo test con acceso mediante
suscripción. Los usuarios pueden registrarse, iniciar sesión, activar una suscripción y
realizar tests con retroalimentación inmediata.

## Características

- Registro e inicio de sesión con contraseñas cifradas.
- Activación de suscripción mensual o anual (simulada) para desbloquear los tests.
- Panel personal con acceso a resultados recientes.
- Catálogo de tests con preguntas tipo test y respuestas correctas.
- Resultados detallados con desglose de respuestas.

## Requisitos

- Python 3.10+
- [pip](https://pip.pypa.io/)

## Instalación

1. Crear y activar un entorno virtual (opcional pero recomendado):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   ```

2. Instalar las dependencias necesarias:

   ```bash
   pip install -r requirements.txt
   ```

3. Ejecutar la aplicación Flask:

   ```bash
   flask --app app run --debug
   ```

4. Accede a `http://127.0.0.1:5000/` en tu navegador. Al iniciar la aplicación se crea una
   base de datos SQLite con datos de ejemplo.

## Estructura principal

```
app.py              # Aplicación Flask y rutas
templates/          # Plantillas HTML de Jinja2
static/styles.css   # Estilos base de la interfaz
```

## Notas

- La lógica de pago está simulada para simplificar la demo.
- Las contraseñas se almacenan cifradas usando Werkzeug.
- Si deseas reiniciar la base de datos, elimina el archivo `instance/cursosgc.sqlite` y vuelve a iniciar la aplicación.
