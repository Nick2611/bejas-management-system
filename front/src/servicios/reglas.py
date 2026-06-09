import pandas as pd

""" Convierte el valor a string limpio:
- NaN/None = ''
- Elimina espacios
- Elimina '.0' si aparece al final
"""
def limpiar_id(valor): #Para la regla 2
    if pd.isna(valor):
        return ''
    s = str(valor).strip()
    return s[:-2] if s.endswith(".0") else s


#---Regla 1, columna K:  =IF($H4="EXPRESS";$A4;$G4) !!!-
def regla_codigo_tienda(df_ssfConversion):
    df_ssfConversion["Cod Tienda"] = df_ssfConversion.apply(
        lambda fila: fila["externalCode"]
        if fila["Parent Department Parent Department name (Label)"] == "EXPRESS"
        else fila["Parent Department parentDepartment (externalCode)"],
        axis=1
    )
    return df_ssfConversion


#---Regla 2, columna L:  =IF($H4="EXPRESS";$A4;$G4) ->True si K existe en columna A de df_customerlocation 
def regla_es_tienda(df_ssfConversion, df_customerlocation):
    #Asegurar que ambas columnas sean string para evitar 0s
    df_ssfConversion["Cod Tienda"] = df_ssfConversion["Cod Tienda"].apply(limpiar_id)
    df_customerlocation["external_id"] = df_customerlocation["external_id"].apply(limpiar_id)

    #tienda = true solo si Cod Tienda no está vacio y existe en customerlocation
    df_ssfConversion["Es Tienda"] = (
        df_ssfConversion["Cod Tienda"].notna()
        & (df_ssfConversion["Cod Tienda"].str.strip() != "")
        & df_ssfConversion["Cod Tienda"].isin(df_customerlocation["external_id"])
    )

    #Dejar solo las que son tienda = true
    df_ssfConversion = df_ssfConversion[df_ssfConversion["Es Tienda"]]
    return df_ssfConversion


#---Regla 3, columna M:   =IF($M7;VLOOKUP(VALUE($L7);customerlocation!$A:$E;2;FALSE);"")
def regla_obtener_id_tienda(df_ssfConversion, df_customerlocation):
    def obtener_id_tienda(fila):
        if fila["Es Tienda"]:  # L = True
            match = df_customerlocation[df_customerlocation["external_id"] == fila["Cod Tienda"]]
            if not match.empty:
                # separar por " - " y tomar el primer elemento (strip para sacar espacios)
                return str(match.iloc[0]["name"]).split("-")[0].strip() # segunda columna en customerlocation
            else:
                return ""
        else:
            return ""
    df_ssfConversion["ID Tienda"] = df_ssfConversion.apply(obtener_id_tienda, axis=1)
    return df_ssfConversion


#---Regla 4, columna N:    =IF($M7;VLOOKUP(VALUE($L7);customerlocation!$A:$E;3;FALSE);"")
def regla_nombre_tienda(df_ssfConversion, df_customerlocation):
    def obtener_nombre_tienda(fila):
        if fila["Es Tienda"]:
            match = df_customerlocation[df_customerlocation["external_id"] == fila["Cod Tienda"]]
            if not match.empty:
                #La columna "name" trae algo como: "827 - Av. Juan B Justo 3695", lo separamos en 2 partes usando " - " como separador
                partes = str(match.iloc[0]["name"]).split("-", 1)

                #Si existen 2 partes, tomamos la segunda (el nombre/dirección de la tienda, si solo hay una parte, devolvemos esa
                return partes[1].strip() if len(partes) > 1 else partes[0].strip()
            else:
                return ""       #Si no encuentra coincidencia en customerlocation
        else:
            return ""       #Si no es tienda, la celda queda vacía
    df_ssfConversion["Nombre Tienda"] = df_ssfConversion.apply(obtener_nombre_tienda, axis=1)
    return df_ssfConversion


#---Regla 5, columna O:    =IF($M7;VLOOKUP(VALUE($L7);customerlocation!$A:$E;4;FALSE);"")
def regla_formato_tienda(df_ssfConversion, df_customerlocation):
    def obtener_formato(fila):
        if fila["Es Tienda"]:
            match = df_customerlocation[df_customerlocation["external_id"] == fila["Cod Tienda"]]
            if not match.empty:
                return match.iloc[0]["customer_location_type"]  # cuarta columna
            else:
                return ""
        else:
            return ""
    df_ssfConversion["Formato"] = df_ssfConversion.apply(obtener_formato, axis=1)
    return df_ssfConversion


#---Regla 6, columna P:     =IF($M8;IF($H8="EXPRESS";"";$F8);"") 
def regla_sector_padre(df_ssfConversion):
    def obtener_sector_padre(fila):
        if fila["Es Tienda"]:
            if fila["Parent Department Parent Department name (Label)"] == "EXPRESS":
                return ""
            else:
                return fila["parentDepartment (Label)"]  # F
        else:
            return ""
    df_ssfConversion["Sector Padre"] = df_ssfConversion.apply(obtener_sector_padre, axis=1)
    return df_ssfConversion


#---Regla 7, columna Q:   =IF($M9;IF($H9="EXPRESS";"";$E9);"")
def regla_codigo_sector_padre(df_ssfConversion):
    def obtener_cod_sector_padre(fila):
        if fila["Es Tienda"]:
            if fila["Parent Department Parent Department name (Label)"] == "EXPRESS":
                return ""
            else:
                return fila["parentDepartment (externalCode)"]  # columna E
        else:
            return ""
    df_ssfConversion["Cod Sector Padre"] = df_ssfConversion.apply(obtener_cod_sector_padre, axis=1)
    return df_ssfConversion


#---Regla 8, columna R:    =IF($M10;IF($H10="EXPRESS";"_TIENDA";$B10);"")
def regla_sector(df_ssfConversion):
    def obtener_sector(fila):
        if fila["Es Tienda"]:
            if fila["Parent Department Parent Department name (Label)"] == "EXPRESS":
                return "_TIENDA"
            else:
                return fila["name (Label)"]  # B
        else:
            return ""
    df_ssfConversion["Sector"] = df_ssfConversion.apply(obtener_sector, axis=1)
    return df_ssfConversion


##---Regla 9, columna S:       =IF($M9;IF($H9="EXPRESS";L9;$A9);"")
def regla_codigo_sector(df_ssfConversion):
    def obtener_codigo_sector(fila):
        if fila["Es Tienda"]:
            if fila["Parent Department Parent Department name (Label)"] == "EXPRESS":
                return fila["Cod Tienda"]  # columna K
            else:
                return fila["externalCode"]  # columna A
        else:
            return ""
    df_ssfConversion["Cod Sector"] = df_ssfConversion.apply(obtener_codigo_sector, axis=1)
    return df_ssfConversion


#---Regla 10, columna T:      =IF($M10;IF(Q10<>"";Q10 & " / ";"") & S10;"")
def regla_descripcion_sector(df_ssfConversion):
    def obtener_descripcion_sector(fila):
        if fila["Es Tienda"]:
            parte_P = f"{fila['Sector Padre']} / " if fila["Sector Padre"] != "" else ""
            return parte_P + fila["Sector"]  # concatenar con R
        else:
            return ""
    df_ssfConversion["Desc Sector"] = df_ssfConversion.apply(obtener_descripcion_sector, axis=1)
    return df_ssfConversion


#---Regla 11, columna U:    Columna Cod. Zona
def regla_codigo_zona(df_ssfConversion):
    def obtener_codigo_zona(fila):
        if fila["Es Tienda"]:
            if fila["Parent Department Parent Department name (Label)"] == "EXPRESS":
                return fila["externalCode"]
            else:
                return ""
        else:
            return ""
    df_ssfConversion["Cod Zona"] = df_ssfConversion.apply(obtener_codigo_zona, axis=1)
    return df_ssfConversion


#---Regla 12, columna V:    Columna Desc. Zona
def regla_descripcion_zona(df_ssfConversion):
    def obtener_descripcion_zona(fila):
        if fila["ID Tienda"]:  
            if fila["Parent Department Parent Department name (Label)"] == "EXPRESS":  
                return fila["parentDepartment (Label)"]  
            else:
                return ""
        else:
            return ""
    df_ssfConversion["Desc Zona"] = df_ssfConversion.apply(obtener_descripcion_zona, axis=1)
    return df_ssfConversion