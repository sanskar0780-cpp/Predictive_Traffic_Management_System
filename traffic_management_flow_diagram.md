# Traffic Management - Process Flow

flowchart LR
    A["Junction Camera Feed"] --> B["Vehicle Detection and Counting"]
    B --> C["Lane and Direction Identification"]
    C --> D["Next Junction Prediction"]
    D --> E["Travel Time Estimation"]
    E --> F["Signal Time Pre-Allocation"]
    F --> G["Green Phase Prepared Before Arrival"]
    G --> H["Vehicles Cross With Minimum Waiting"]
    H --> I["Live Traffic Metrics Updated"]
    I --> B

    J["Emergency Vehicle Detection"] --> K["Priority Signal Override"]
    K --> F

    L["SUMO + TraCI Prototype"] --> B
    I --> M["Dashboard / Impact Metrics"]