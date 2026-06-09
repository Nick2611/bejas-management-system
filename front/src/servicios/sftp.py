import paramiko


hostname = "20.201.65.169"
username = "1159358T"
password = "yN#NuT%D1t81@aI"  # Reemplaza con tu contraseña
remote_path = "/incoming/Portal_Demanda/REPORTE_248/ID248-Depportienda-Page1-Component1.csv"  # Cambia por la ruta y nombre del archivo en el SFTP
local_path = "./Reporte-testing-tienda.csv"  # Cambia por la ruta y nombre donde guardarás el archivo

# Crear cliente SSH
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Forzar algoritmo ssh-rsa
client.connect(
    hostname,
    username=username,
    password=password,
    disabled_algorithms=dict(pubkeys=["rsa-sha2-256", "rsa-sha2-512"]),
)

# Iniciar SFTP y descargar archivo
sftp = client.open_sftp()
sftp.get(remote_path, local_path)
sftp.close()
client.close()
print("Archivo descargado correctamente.")
