# Quickstart

The purpose of this repository is to provide individually functional scripts to demonstrate how to use Five9 Configuration Webservices API methods in Python.

# DISCLAIMER

This repository contains sample code which is **not an official Five9 resource**. It's intended for educational and illustrative purposes only, demonstrating potential ways to utilize APIs in the Five9 contact center environment.

By choosing to use this code, you acknowledge and agree to the following:

- This is **not** officially endorsed or supported software by Five9.
- All customizations, modifications, or deployments made with this code are entirely at your **own risk** and **responsibility**.
- The provided code may not cover all possible use cases or be adapted to your specific needs without further modification.
- Five9 will **not** provide any support or assume any liability for any issues that may arise from the use of this code.

For a fully supported, robust, and tailor-made solution, we highly recommend consulting with Five9's professional services team. Utilizing their expertise ensures a reliable and efficient setup that meets your specific needs, and comes with the added benefit of official support.

# Obtaining the repository

It is highly recommended that you install [git](https://git-scm.com/download/win) so that you can update to the latest version of this repository as needed.  Once installed, from the command line you can clone this repository with

    git clone https://github.com/andrewawilley/Five9-Configuration-Webservices-API-Samples.git

You can also just download a [zip archive](https://github.com/andrewawilley/Five9-Configuration-Webservices-API-Samples/archive/refs/heads/main.zip) of the repository and extract

from the shell, navigate to the local copy (change to the directory that the repository is located) and then ...

#### Windows Users
    mkdir venvs
    cd venvs
    py.exe -m venv five9
    cd ..
    .\venvs\five9\Scripts\activate

#### Mac/Linux Users
    mkdir venvs
    cd venvs
    python3 -m venv five9
    cd ..
    source venvs/five9/bin/activate

### finishing up
    pip install -e .

The setup script will create a private folder that can contain a credentials.py file where you can keep reusable Five9 admin API user credentials in a slightly more secure way than right in the script.  The private folder is excluded from Git.  

The credentials object in private.credentials looks like this:

    ACCOUNTS = {
        'default_account': {
            'username': 'apiUserName',
            'password': 'superSecretPassword'
        }
    }

If you run a script without this accounts object, you'll be prompted to enter username and password in the console. 

# Creating and using a shell session
After activating the virtual evnironment, launch an interactive shell session with the included five9_session.py

When executed on its own, it will launch an interactive shell that can be used to test API calls.  For example:

    python five9_session.py
    https://api.five9.com/wsadmin/v12/?wsdl&user=clutch_vcc@aw_tam
    Client ready for clutch_vcc@aw_tam
    Python 3.11.3 (tags/v3.11.3:f3909b8, Apr  4 2023, 23:49:59) [MSC v.1934 64 bit (AMD64)] on win32
    Type "help", "copyright", "credits" or "license" for more information.
    (InteractiveConsole)
    >>> users = client.service.getUsersGeneralInfo()
    >>> print(users)

By default the session will use the default_account credentials from the private.credentials file.  If you want to use a different account, you can specify it as an argument to the script such as:

    python five9_session.py --account my_other_account

You can also provide the username and password as arguments to the script

    python five9_session.py --username apiUserName --password superSecretPassword

Adding the "-go" flag will also obtain the domain 'users', 'campaigns', and 'skills' as variables in the shell

    python five9_session.py -go

The Five9Client in the five9_session script can be used in other scripts as well.  For example, in another script you can import the Five9Client class and create a client object like this:

    from five9_session import Five9Client
    client = five9_session.Five9Client()

## Using the client object

An authenticated client object can invoke any of the API endpoints.  For example:

    call_variables = client.service.getCallVariables()

The most recent SOAP envelope content can be viewed with 

    print(client.latest_envelopes)

To print all of the client methods available from the service definition file
    
    client.print_available_service_methods()

The available methods as of v12 are:

    addDNISToCampaign
    addDispositionsToCampaign
    addListsToCampaign
    addNumbersToDnc
    addPromptTTS
    addPromptWav
    addPromptWavInline
    addRecordToList
    addRecordToListSimple
    addSkillAudioFile
    addSkillsToCampaign
    addToList
    addToListCsv
    addToListFtp
    asyncAddRecordsToList
    asyncDeleteRecordsFromList
    asyncUpdateCampaignDispositions
    asyncUpdateCrmRecords
    checkDncForNumbers
    closeSession
    createAgentGroup
    createAutodialCampaign
    createCallVariable
    createCallVariablesGroup
    createCampaignProfile
    createContactField
    createDisposition
    createIVRScript
    createInboundCampaign
    createList
    createOutboundCampaign
    createReasonCode
    createSkill
    createSpeedDialNumber
    createUser
    createUserProfile
    createWebConnector
    deleteAgentGroup
    deleteAllFromList
    deleteCallVariable
    deleteCallVariablesGroup
    deleteCampaign
    deleteCampaignProfile
    deleteContactField
    deleteFromContacts
    deleteFromContactsCsv
    deleteFromContactsFtp
    deleteFromList
    deleteFromListCsv
    deleteFromListFtp
    deleteIVRScript
    deleteLanguagePrompt
    deleteList
    deletePrompt
    deleteReasonCode
    deleteReasonCodeByType
    deleteRecordFromList
    deleteSkill
    deleteUser
    deleteUserProfile
    deleteWebConnector
    forceStopCampaign
    getAgentGroup
    getAgentGroups
    getApiVersions
    getAutodialCampaign
    getAvailableLocales
    getCallCountersState
    getCallVariableGroups
    getCallVariables
    getCampaignDNISList
    getCampaignProfileDispositions
    getCampaignProfileFilter
    getCampaignProfiles
    getCampaignState
    getCampaignStrategies
    getCampaigns
    getConfigurationTranslations
    getContactFields
    getContactRecords
    getCrmImportResult
    getDNISList
    getDialingRules
    getDisposition
    getDispositions
    getDispositionsImportResult
    getIVRScripts
    getInboundCampaign
    getIvrIcons
    getIvrScriptOwnership
    getListImportResult
    getListsForCampaign
    getListsInfo
    getLocale
    getOutboundCampaign
    getPrompt
    getPrompts
    getReasonCode
    getReasonCodeByType
    getReportResult
    getReportResultCsv
    getSkill
    getSkillAudioFiles
    getSkillInfo
    getSkillVoicemailGreeting
    getSkills
    getSkillsInfo
    getSpeedDialNumbers
    getUserGeneralInfo
    getUserInfo
    getUserProfile
    getUserProfiles
    getUserVoicemailGreeting
    getUsersGeneralInfo
    getUsersInfo
    getVCCConfiguration
    getWebConnectors
    isImportRunning
    isReportRunning
    modifyAgentGroup
    modifyAutodialCampaign
    modifyCallVariable
    modifyCallVariablesGroup
    modifyCampaignLists
    modifyCampaignProfile
    modifyCampaignProfileCrmCriteria
    modifyCampaignProfileDispositions
    modifyCampaignProfileFilterOrder
    modifyContactField
    modifyDisposition
    modifyIVRScript
    modifyInboundCampaign
    modifyOutboundCampaign
    modifyPromptTTS
    modifyPromptWav
    modifyPromptWavInline
    modifyReasonCode
    modifySkill
    modifyUser
    modifyUserCannedReports
    modifyUserProfile
    modifyUserProfileSkills
    modifyUserProfileUserList
    modifyVCCConfiguration
    modifyWebConnector
    removeDNISFromCampaign
    removeDisposition
    removeDispositionsFromCampaign
    removeIvrIcons
    removeIvrScriptOwnership
    removeListsFromCampaign
    removeNumbersFromDnc
    removeSkillAudioFile
    removeSkillsFromCampaign
    removeSpeedDialNumber
    renameCampaign
    renameDisposition
    resetCampaign
    resetCampaignDispositions
    resetListPosition
    runReport
    setCampaignStrategies
    setDefaultIVRSchedule
    setDialingRules
    setIvrIcons
    setIvrScriptOwnership
    setLocale
    setSkillVoicemailGreeting
    setUserVoicemailGreeting
    startCampaign
    stopCampaign
    updateConfigurationTranslations
    updateContacts
    updateContactsCsv
    updateContactsFtp
    updateCrmRecord
    updateDispositions
    updateDispositionsCsv
    updateDispositionsFtp
    userSkillAdd
    userSkillModify
    userSkillRemove
