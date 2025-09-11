import os
import time
import tqdm
from five9.utils.common import common_parser_arguments, create_five9_client


def get_campaigns_by_campaign_status(client, target_status):
    campaigns = client.service.getCampaigns()

    target_campaigns = []
    for campaign in campaigns:
        if campaign.state == target_status:
            target_campaigns.append(campaign)

    return target_campaigns


# if main script
if __name__ == "__main__":
    additional_args = [
        {
            "name": "--fields_to_remove",
            "type": str,
            "required": True,
            "help": "List of contact fields to remove (pipe delimited)",
        }
    ]
    args = common_parser_arguments(additional_args)

    # create a list from the fields to remove, assume they are pipe-delimited
    fields_to_remove = args.fields_to_remove.split("|")

    # Create Five9 client
    client = create_five9_client(args)

    # Fetch all running campaigns
    originally_running_campaigns = get_campaigns_by_campaign_status(client, "RUNNING")

    if originally_running_campaigns:
        # create the /private subfolder if it doesn't exist
        os.makedirs("private", exist_ok=True)

        # write the list of running campaigns to a file in the /private subfolder
        with open("private/running_campaigns.txt", "w") as f:
            for campaign in originally_running_campaigns:
                f.write(f"{campaign.name}\n")

        # using tqdm, stop running campaigns
        with tqdm.tqdm(
            total=len(originally_running_campaigns),
            desc="Requesting campaigns to stop",
            mininterval=1,
        ) as pbar:
            for campaign in originally_running_campaigns:
                try:
                    client.service.stopCampaign(campaign.name)
                    time.sleep(0.3)
                except Exception as e:
                    print(f"\nFAILED to stop campaign '{campaign.name}': {e}\n")
                finally:
                    pbar.update(1)
                    pbar.set_postfix({"Stops Requested": pbar.n})

        # wait 3 seconds
        print("\nWaiting 3 seconds for campaigns to stop...\n")
        time.sleep(3)

        # get all campaigns that are stopping
        campaigns_in_stopping = get_campaigns_by_campaign_status(client, "STOPPING")
        campaigns_in_stopping_count = len(campaigns_in_stopping)
        if len(campaigns_in_stopping) > 0:
            print(
                f"\n{campaigns_in_stopping_count} campaigns are still stopping. Waiting for them to stop...\n"
            )
            with tqdm.tqdm(
                total=campaigns_in_stopping_count,
                desc="Monitoring STOPPING status campaigns (5 seconds)",
                mininterval=1,
            ) as pbar:
                while len(campaigns_in_stopping) > 0:
                    campaigns_in_stopping = get_campaigns_by_campaign_status(
                        client, "STOPPING"
                    )
                    campaigns_in_stopping_still_count = len(campaigns_in_stopping)
                    pbar.set_postfix(
                        {"Campaigns still STOPPING": campaigns_in_stopping_still_count}
                    )
                    pbar.update(
                        campaigns_in_stopping_count - campaigns_in_stopping_still_count
                    )
                    time.sleep(5)

        print("\nAll campaigns are stopped.\n")

        # remove specific contact fields
        print(f"\nRemoving fields: {fields_to_remove}")
        for field in fields_to_remove:
            try:
                client.service.deleteContactField(field)
                print(f"\tDeleted field '{field}'")
            except Exception as e:
                print(f"\tFAILED to delete field '{field}': {e}\n")

        print("\nAll targeted fields removed.\n")
        # restart all previously running campaigns
        with tqdm.tqdm(
            total=len(originally_running_campaigns),
            desc="Requesting campaigns to start",
            mininterval=1,
        ) as pbar:
            for campaign in originally_running_campaigns:
                try:
                    client.service.startCampaign(campaign.name)
                    time.sleep(0.3)
                except Exception as e:
                    print(f"\nFAILED to start campaign '{campaign.name}': {e}\n")
                finally:
                    pbar.update(1)
                    pbar.set_postfix({"Started": pbar.n})
    else:
        print("\nNo running campaigns found.\n")

    # get the list of running campaigns
    running_campaigns_after_process = get_campaigns_by_campaign_status(
        client, "RUNNING"
    )

    if len(running_campaigns_after_process) == len(originally_running_campaigns):
        print("\nAll campaigns restarted successfully.\n")
    else:
        print("\nSome campaigns failed to restart.\n")
        # print the list of campaigns that failed to restart
        failed_campaigns = list(
            set(originally_running_campaigns) - set(running_campaigns_after_process)
        )
        for campaign in failed_campaigns:
            print(f"\t{campaign.name}")
