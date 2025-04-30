# Complex Event Processing for Root Causes

Unlike other modules, which focus on a specific power substation, this **Complex Event Processing (CEP)** module operates at a **city or large-region scale**. It receives **telemetry data every minute** from all energy consumer units in the area.

## Overview

For example, considering **Uberlândia**, which has around **300,000 consumer units**, the module processes **300k telemetry packets per minute**. Its role is to:  
- Analyze these packets  
- Detect basic events  
- Attempt to correlate them to **root causes**  

## Key Functionality

One of the key tasks is **identifying widespread power outages**. If thousands of outage reports are received simultaneously, the module:  
1. Attempts to **correlate** them  
2. Generates a **single alarm**  
3. Sends this alarm to **Module 3**, indicating the number of alarms grouped into a single event  

🚀 This module plays a crucial role in optimizing power grid monitoring and fault detection.  

Project Setup

Follow these steps to set up your local environment:

1. Create and Activate Virtual Environment

On macOS/Linux:

python3 -m venv venv
source venv/bin/activate

On Windows:

python -m venv venv
.\venv\Scripts\activate

2. Install Dependencies

Install all the necessary packages listed in requirements.txt:

pip install -r requirements.txt