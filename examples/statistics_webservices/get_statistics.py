import logging

import time

from five9.five9_session import Five9Client

logging.basicConfig(level=logging.INFO)


class Five9Statistics:
    def __init__(
        self,
        client,
        statistics_request_type,
        statistics_request_columns=None,
        long_polling_timeout=5000,
        update_timeout_seconds=5,
    ):
        self.client = client
        self.statistics_request_type = statistics_request_type
        self.statistics_request_columns = statistics_request_columns

        self.long_polling_timeout = long_polling_timeout
        
        self.update_timeout_seconds = update_timeout_seconds
        self.last_checked_timestamp = 0


        self.statistics = None
        self.statistics_timestamp = None

    def get_statistics(self):
        if self.statistics_request_columns is not None:
            self.statistics = self.client.service.getStatistics(
                statisticType=self.statistics_request_type,
                columnNames=self.statistics_request_columns,
            )
            
        else:
            self.statistics = self.client.service.getStatistics(
                self.statistics_request_type
            )

        self.last_checked_timestamp = time.time()
        self.statistics_timestamp = self.statistics.timestamp
        logging.info(f"Initial statistics for {self.statistics_request_type} obtained at {self.last_checked_timestamp}, next update in {self.update_timeout_seconds} seconds")

    def get_statistics_update(self):
        try:
            # if the current time is greater than the last checked timestamp plus the update timeout, then get the update
            if time.time() > self.last_checked_timestamp + self.update_timeout_seconds:
                logging.info(f"\n\n{self.statistics_request_type}\t last checked at {self.last_checked_timestamp}")
                self.statistics = self.client.service.getStatisticsUpdate(
                    statisticType=self.statistics_request_type,
                    previousTimestamp=self.statistics_timestamp,
                    longPollingTimeout=self.long_polling_timeout,
                )
                self.statistics_timestamp = self.statistics.lastTimestamp
                logging.debug(self.client.latest_envelope_received)
                logging.info(self.statistics)
                # update the last checked timestamp to the current time in milliseconds
                self.last_checked_timestamp = time.time()
        except AttributeError:
            logging.info(
                f"{self.statistics_request_type} UNCHANGED since {self.statistics_timestamp}"
            )
            logging.info(self.statistics)
            self.last_checked_timestamp = time.time()




if __name__ == "__main__":
    client = Five9Client(sessiontype="statistics")

    # these default settings can be changed to suit your needs
    view_settings = {
        "forceLogoutSession": "yes",
        # [Minutes5,Minutes10,Minutes15,Minutes30,Hour1,Hours2,Hours3,Today]
        "rollingPeriod": "Today",
        "shiftStart": "28800000",
        "statisticsRange": "CurrentWeek",
        "timeZone": "-25200000",
    }
    client.session_parameters = client.service.setSessionParameters(
        viewSettings=view_settings
    )


    print(client.latest_envelopes)

    # Create a list of statistics to get
    stats = [
        # Five9Statistics(
        #     client,
        #     "AgentState",
        #     statistics_request_columns={
        #         "values": {"data": ["Username", "Full Name", "State", "State Since"]}
        #     },
        # ),
        # Five9Statistics(
        #     client,
        #     "AgentStatistics"
        # ),
        Five9Statistics(
            client,
            "InboundCampaignStatistics"
        )
    ]

    # Get the initial statistics
    for stat in stats:
        stat.get_statistics()

    print(client.latest_envelope_sent)

    # Get the statistics updates
    while True:
        for stat in stats:
            stat.get_statistics_update()

        # sleep for five seconds to avoid overwhelming the server
        time.sleep(5)
        print(client.latest_envelope_sent)
