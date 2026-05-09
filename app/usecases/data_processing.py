from app.entities.agent_data import AgentData
from app.entities.processed_agent_data import ProcessedAgentData


def process_agent_data(agent_data: AgentData) -> ProcessedAgentData:
    """
    Process agent data and classify the state of the road surface.
    Parameters:
        agent_data (AgentData): Agent data that containing accelerometer, GPS, and timestamp.
    Returns:
        processed_data_batch (ProcessedAgentData): Processed data containing the classified state of the road surface and agent data.
    """

    x = agent_data.accelerometer.x
    y = agent_data.accelerometer.y
    z = agent_data.accelerometer.z

    peak_value = max(abs(x), abs(y), abs(z))

    if peak_value > 4.0:
        road_state = "pothole"
    elif peak_value > 1.5:
        road_state = "roughness"
    else:
        road_state = "normal"

    return ProcessedAgentData(
        road_state=road_state,
        agent_data=agent_data
    )