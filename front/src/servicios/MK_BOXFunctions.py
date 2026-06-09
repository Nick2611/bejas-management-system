from boxsdk import Client, OAuth2
import json
import requests
import os
import logging

# ## Sacar ##
# import dotenv
# dotenv.load_dotenv()
# ###


def _get_box_config():
    required_vars = [
        "BOXCLIENTID",
        "BOXCLIENTSECRET",
        "BOXENTERPRISEID",
        "BOXIDMAINFOLDER",
    ]
    config = {}
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            raise ValueError(f"Variable de entorno requerida no encontrada: {var}")
        config[var] = value
    return config


def extractFolderNameFileName(
    pathFile,
):  # str --> ["folder/file.txt"] #Result = ["folder","file.txt"]
    result = pathFile.split("/")
    return result


def get_access_token(enterprise_id, client_id, client_secret):
    """
    Get the Box access token
    | Extraido de https://github.ibm.com/harrisw/gpra-automation/blob/master/box_service.py
    """
    url = "https://api.box.com/oauth2/token"

    subject_id = enterprise_id  # enterprise_ID >> configurations.
    subject_type = "enterprise"
    type = "client_credentials"
    payload = f"client_id={client_id}& \
            client_secret={client_secret}& \
            grant_type={type}&box_subject_type={subject_type}& \
            box_subject_id={subject_id}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        response = requests.request("POST", url, data=payload, headers=headers)
    except Exception as err:
        raise Exception(f"ERROR Getting BOX API access token: {str(err)}")

    json_response = response.json()
    # print(json_response)

    return json_response["access_token"]


def myObjectsList():  # Mockeado
    ##List object of Bucket
    mockList = ["test-folder01/testfile1.txt", "test-folder01/testfile2.txt"]
    return mockList


def generateClientAuth(
    myClientId: str, myClientSecret: str, myAccessToken: str
):  ##Return client, auth
    try:
        auth = OAuth2(
            client_id=myClientId,
            client_secret=myClientSecret,
            access_token=myAccessToken,  # Ver como conseguir el token.
        )

        client = Client(auth)
    except Exception:
        logging.exception("Error al crear cliente de Box")
        exit(-1)
    return client


def uploadFileToBox(
    client, folder_id: str, urlFile: str
):  # filderID = '9999' #urlFile './myFile.txt'
    try:
        logging.info(f"Uploading file {urlFile} | uploadFileToBox.")
        client.folder(folder_id).upload(urlFile)
        logging.info("Succesful upload | uploadFileToBox.")
    except Exception as exc:
        logging.error(f"{exc} Error | uploadFileToBox.")  # Enviar msj slack.
        exit(-1)


def createASubFolder(
    client, folder_id: str, newFolderName: str
):  # folder_id = '99' #newFolderName 'testingFolder' #return subfolder id.
    try:
        logging.info(f"Creating subfolder {newFolderName}")
        subfolder = client.folder(folder_id).create_subfolder(newFolderName)
        logging.info(f"Created subfolder with ID: {subfolder.id}")
    except Exception as exc:
        if exc.status == 409:
            logging.error(f"Error: {exc.message} {newFolderName} | createASubFolder.")
            datos = str(exc.context_info)
            data = json.loads(
                datos.replace("'", '"')
            )  # Reemplazar comillas simples por comillas dobles
            id_value = data["conflicts"][0]["id"]
            logging.info(f"folderID: {id_value}")
            return id_value

        else:
            logging.error(f"{exc}\nError | createASubFolder.")  # Enviar msj slack.
            # print(f"STATUS CODE: {exc.status}")
            exit(-1)

    logging.info(f"FolderID: {subfolder.id}")
    return subfolder.id


##Uploading files Of new subfolder.
def uploadFilesOfList(
    client, folder_id: str, fileList
):  # filderID = '9999' #fileList = vec[str] =['blabla/blabla','bla/bla']
    try:
        for objectPath in fileList:
            uploadFileToBox(client, folder_id, objectPath)
    except Exception as exc:
        logging.error(f"{exc} Error | uploadFilesOfFolder.")  # Enviar msj slack.
        exit(-1)


def listItemsOfFolder(client, folder_id: str):
    try:
        items = client.folder(folder_id).get_items()
        logging.info("\nItems on folder:")
        for item in items:
            logging.info(f'{item.type.capitalize()} {item.id} is named "{item.name}"')
            # print(f'{item.type.capitalize()} {item.id} is named "{item.name}"')
        logging.info("")
    except Exception as exc:
        logging.error(f"{exc} Error | listItemsOfFolder.")
        exit(-2)


def downloadObject(client, file_id, pathDestFile):
    try:
        file_content = client.file(file_id).content()

        logging.info("FileName {pathDestFile}")
        with open(pathDestFile, "wb") as f_result:
            f_result.write(file_content)

        logging.info(f"The file {pathDestFile} has been downloaded succesful")
    except Exception as exc:
        logging.error(f"{exc} Error | downloadObject.")  # Enviar msj slack.
        exit(-1)


def uploadExistingFile(client, file_id, pathSrctFile):
    # file_id = '11111'
    # file_path = '/path/to/file.pdf'
    try:
        updated_file = client.file(file_id).update_contents(pathSrctFile)
        logging.info(f"File {updated_file.name} has been updated")

    except Exception as exc:
        logging.error(f"{exc} Error | uploadExistingFile.")  # Enviar msj slack.
        exit(-1)


def removefile(client, file_id):
    ##print(f"**Removing file with ID {file_id}**")
    try:
        client.file(file_id).delete()
        logging.info(f"File with ID {file_id} has been removed")
        # print(f"File with ID {file_id} has been removed")
    except Exception as exc:
        logging.error(f"{exc} Error | removefile.")  # Enviar msj slack.
        # print(f"{exc} Error | removefile.")
        exit(-1)


def returnClient():
    box_config = _get_box_config()
    accessToken = get_access_token(
        box_config["BOXENTERPRISEID"],
        box_config["BOXCLIENTID"],
        box_config["BOXCLIENTSECRET"],
    )
    client = generateClientAuth(
        box_config["BOXCLIENTID"], box_config["BOXCLIENTSECRET"], accessToken
    )
    return client


def upload_process_files_to_box(destFolderName):
    box_config = _get_box_config()
    accessToken = get_access_token(
        box_config["BOXENTERPRISEID"],
        box_config["BOXCLIENTID"],
        box_config["BOXCLIENTSECRET"],
    )
    client = generateClientAuth(
        box_config["BOXCLIENTID"], box_config["BOXCLIENTSECRET"], accessToken
    )

    newFolderName_id = createASubFolder(
        client, box_config["BOXIDMAINFOLDER"], destFolderName
    )

    csv_files = []
    for filename in os.listdir(destFolderName):
        if filename.endswith(".csv"):
            csv_files.append(os.path.join(destFolderName, filename))

    uploadFilesOfList(client, newFolderName_id, csv_files)


def download_items_of_folder(client, folderId, nameDestFolder):
    idsOfItems = []
    items = client.folder(folderId).get_items()
    for item in items:
        if item.type == "file":
            file_id = item.id
            pathDestFile = os.path.join(nameDestFolder, item.name)
            downloadObject(client, file_id, pathDestFile)
            idsOfItems.append(item.id)

    return idsOfItems
