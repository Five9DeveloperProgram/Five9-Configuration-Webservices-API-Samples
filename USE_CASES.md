# What can you build with this library?

**Build your own Five9 administration tooling by combining Configuration
Webservices API methods.** The Python client handles the SOAP connection and
authentication so you can compose the API methods available to your account:
read configuration, compare objects, produce a plan, make targeted changes,
and verify the result. The [example scripts](examples/) show complete,
adaptable workflows; the pre-built [utilities](five9/utils/) provide reusable
pieces you can import into your own scripts instead of starting from scratch.
Together they are starting points for new use cases, not a claim that every
API operation has a ready-made script.

## Reusable building blocks

- [Client and CLI helpers](five9/utils/common.py) handle standard arguments
  and client creation for your own examples.
- [Domain capture](five9/utils/domain_capture.py) and
  [campaign-profile sync helpers](five9/utils/campaign_profile_sync.py) help
  you retrieve configuration, compare profiles and filters, and plan changes.
- [IVR analysis](five9/utils/ivr_utils.py) and
  [diagram generation](five9/utils/ivr_diagram.py) can turn IVR definitions
  into function/variable inventories and visual documentation.

The use cases below link to both runnable examples and, where useful, the
utilities behind them. Adapt the parts you need to build your own workflow.

## Explore, document, and compare a domain

- **Capture a domain configuration snapshot** of skills, prompts, dispositions,
  call variables, contact fields, agent groups, campaign profiles, campaigns,
  IVRs, and other supported objects. Keep the results in version control to
  review changes or prepare a migration:
  [domain configuration capture](examples/domain_config/domain_config_capture.py)
  and [snapshot utility](five9/utils/domain_capture.py).
- **Turn IVR XML into readable documentation:** generate SVG call-flow diagrams
  and text/Markdown summaries; inventory variables, skill transfers, and
  JavaScript functions across scripts:
  [IVR diagrams](examples/ivrs/ivr_generate_diagrams.py),
  [variable usage](examples/ivrs/ivr_variable_usage.py),
  [skill transfers](examples/ivrs/skill_transfer_module_usage.py), and
  [JavaScript function export](examples/ivrs/export_jsFunctions_from_ivr.py).
- **Understand campaign-profile filters** by translating their criteria and
  grouping expressions into a more readable form:
  [filter inspection](examples/domain_config/domain_campaign_pf_demystify.py)
  and [filter utility](five9/utils/campaign_profile_comprehension.py).

## Manage users and access

- **Create or update users in bulk** from a template or CSV, assign or remove
  skills, and update federation IDs:
  [bulk user creation](examples/user_management/bulk_user_create.py),
  [CSV updates](examples/user_management/bulk_user_update_from_csv.py),
  [skill assignments](examples/user_management/bulk_user_skill_update.py), and
  [federation ID updates](examples/user_management/bulk_user_federationId_update_from_csv.py).
- **Audit users or prepare a migration:** export user details to CSV, review
  recording permissions, or adjust selected roles:
  [user export](examples/user_management/capture_user_detail_to_csv.py),
  [recording permission example](examples/user_management/bulk_remove_recording_permission.py),
  and [migration preparation](examples/user_management/migration_user_prep.py).

## Work with campaigns, profiles, and IVRs

- **Move selected configuration between domains:** capture the source, preview
  what differs in the destination, then selectively create or update outbound
  campaigns and campaign profiles, including profile filters:
  [campaign transfer](examples/domain_config/push_campaigns.py) and
  [profile transfer](examples/domain_config/push_campaign_profiles.py).
- **Adapt configuration for specific operational needs:** add call variables
  to profiles, adjust campaign-profile stop times, or upload multilingual
  prompt audio:
  [call variables](examples/bulk_add_call_variable_to_profiles.py),
  [stop times](examples/domain_config/bulk_update_campaign_profile_stop_time.py),
  and [prompts](examples/prompt_management/multilingual_prompt.py).

## Update contact and list data

- **Add or remove list records**, one at a time or through the available
  asynchronous and CSV operations:
  [list record examples](examples/records_management/).
- **Update contact/CRM fields from CSV** using synchronous or asynchronous
  API methods:
  [contact updates](examples/records_management/contact_updateContactsCsv.py)
  and [async CRM updates](examples/records_management/contact_asyncUpdateCrmRecords.py).

## Retrieve reports and live statistics

- **Run an existing Five9 report** and retrieve its CSV results. The report
  definition must already exist in Five9:
  [report example](examples/reporting/runReport.py) and
  [reporting notes](examples/reporting/README.md).
- **Monitor agent, queue, and campaign statistics** with an initial snapshot
  and optional incremental updates. This uses a statistics session rather
  than the admin configuration session:
  [statistics example](examples/statistics_webservices/get_statistics.py)
  and [statistics notes](examples/statistics_webservices/README.md).

These are sample scripts, not production-ready automation. Review each
example and use a dry run or small test subset before a bulk change; confirm
the target domain before any write. Deletions and renames require the
[object dependency and safe deletion guide](OBJECT_DEPENDENCIES.md).
