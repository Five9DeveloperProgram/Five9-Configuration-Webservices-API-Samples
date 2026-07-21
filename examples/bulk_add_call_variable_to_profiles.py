"""
Bulk add a specific Call Variable to multiple campaign profile layouts.

This script demonstrates how to:
1. Retrieve all campaign profiles or a filtered list
2. Get the current layout for each profile
3. Add a specific Call Variable to the layout if not already present
4. Update the campaign profile with the modified layout

Usage:
    python bulk_add_call_variable_to_profiles.py --account_alias default_account --call-variable-name "MyVariable"
"""

from five9.utils.common import common_parser_arguments, create_five9_client
from tqdm import tqdm
import logging

if __name__ == "__main__":
    # Parse arguments
    parser = common_parser_arguments(
        additional_args=[
            {
                "name": "--call-variable-name",
                "type": str,
                "required": True,
                "help": "Name of the Call Variable to add to layouts"
            },
            {
                "name": "--profile-pattern",
                "type": str,
                "default": ".*",
                "help": "Regex pattern to filter campaign profiles (default: all profiles)"
            },
            {
                "name": "--dry-run",
                "action": "store_true",
                "help": "Show what would be changed without making actual updates"
            }
        ]
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    # Create Five9 client
    logger.info("Creating Five9 client...")
    client = create_five9_client(args)
    
    # First, let's inspect what getCampaignProfiles returns
    logger.info(f"Fetching campaign profiles matching pattern: {args.profile_pattern}")
    try:
        profiles = client.service.getCampaignProfiles(
            profileNamePattern=args.profile_pattern
        )
        
        if not profiles:
            logger.warning("No campaign profiles found")
            exit(0)
        
        logger.info(f"Found {len(profiles)} campaign profile(s)")
        
        # Inspect the first profile to see structure
        if profiles:
            logger.info("\n=== Inspecting first profile structure ===")
            first_profile = profiles[0]
            logger.info(f"Profile name: {first_profile.name}")
            logger.info(f"Profile type: {type(first_profile)}")
            logger.info(f"Profile attributes: {dir(first_profile)}")
            
            # Check if profile has layout-related attributes
            for attr in dir(first_profile):
                if not attr.startswith('_'):
                    value = getattr(first_profile, None)
                    logger.info(f"  {attr}: {value}")
        
    except Exception as e:
        logger.error(f"Error fetching campaign profiles: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
