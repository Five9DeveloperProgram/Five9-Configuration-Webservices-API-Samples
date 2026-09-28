# Domain config snapshot capture example

Before deleting or renaming a domain object, use the repository's
[object dependency and safe deletion guide](../../OBJECT_DEPENDENCIES.md).
It describes which snapshot files and additional live API checks can reveal
references to the target object.

The domain capture example can be run from the command line. You can provide a
username and password argument or provide the account alias as stored in the
`private/credentials.py` file.

Certain methods such as getCampaigns, getSkills, and getCampaignProfiles respond with a configuration object that requires an additional call to a corresponding detail method to obtain more information about the target objects.  In these cases, the script is configured to iterate through the objects in the response and store the additional detail in a subfolder.  For the getCampaigns method, the method needed to obtain the campaign details depends on the campaign type (inbound or outbound).  In this case, it will store the campaign details in a campaigns_inbound and campaigns_outbound folder accordingly.  

The getIVRScripts method returns all IVRs in a single object, so this script iterates through all of the IVRs returned and stores them in individual files in the ivrs folder.  
