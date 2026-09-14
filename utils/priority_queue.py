import heapq


class PriorityQueueManager:

    def __init__(self):

        # Lower value = Higher Priority
        self.priority_map = {
            "Critical": 1,
            "Urgent": 1,
            "High": 2,
            "Medium": 3,
            "Low": 4
        }

    # ------------------------------------
    # Escalate Priority
    # ------------------------------------

    def calculate_effective_priority(
        self,
        ai_priority,
        related_reports
    ):

        priority = ai_priority

        if related_reports >= 6:

            priority = "Critical"

        elif related_reports >= 4:

            if ai_priority == "Medium":
                priority = "High"

            elif ai_priority == "High":
                priority = "Critical"

        elif related_reports >= 2:

            if ai_priority == "Low":
                priority = "Medium"

            elif ai_priority == "Medium":
                priority = "High"

        return priority

    # ------------------------------------
    # Build Priority Queue
    # ------------------------------------

    def build_priority_queue(self, complaints):

        heap = []

        for complaint in complaints:

            effective_priority = self.calculate_effective_priority(
                complaint["priority"],
                complaint["related_reports"]
            )

            complaint["effective_priority"] = effective_priority

            heapq.heappush(

                heap,

                (
                    self.priority_map.get(effective_priority, 3),
                    complaint["id"],
                    complaint
                )

            )

        ordered = []

        while heap:

            ordered.append(
                heapq.heappop(heap)[2]
            )

        return ordered