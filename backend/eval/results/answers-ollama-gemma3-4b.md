## End to end: 184 golden questions, 2026-10-20

Chat model `ollama:gemma3:4b`, embeddings `qwen3-embedding:4b`, retrieval `dense`. *Routed*: the pipeline took the expected path (answer, refuse, tool, handoff). *Correct*: routed, every expected fact present, no forbidden fact (e.g. another market's number). *Cites relevant*: an answer cites a passage from the expected section.

Latency per question: median 8.2 s, p95 18.2 s.

| Category | n | Routed | Correct | Cites relevant | Judge: faithful | Judge: correct |
|---|---|---|---|---|---|---|
| cross_lingual | 8 | 100% | 88% | 100% | 100% | 88% |
| followup | 10 | 90% | 80% | 70% | 89% | 89% |
| german | 20 | 100% | 95% | 95% | 100% | 95% |
| handoff | 3 | 100% | 100% | – | – | – |
| injection | 6 | 100% | 100% | 100% | 100% | 100% |
| keyword | 12 | 92% | 75% | 92% | 100% | 82% |
| market | 9 | 89% | 78% | 78% | 100% | 75% |
| model | 18 | 100% | 89% | 94% | 75% | 88% |
| multi_doc | 3 | 67% | 0% | 33% | 50% | 0% |
| natural | 60 | 100% | 87% | 92% | 95% | 86% |
| out_of_scope | 10 | 100% | 100% | – | – | – |
| pii | 4 | 75% | 75% | 75% | 100% | 100% |
| public | 8 | 75% | 75% | 62% | 83% | 100% |
| tool_charger | 5 | 100% | 100% | – | – | – |
| tool_recall | 5 | 100% | 100% | – | – | – |
| version | 3 | 100% | 100% | 100% | 100% | 100% |
| **all** | 184 | 96% | 86% | 88% | 93% | 87% |

Judge `groq:qwen/qwen3.8-27b` graded 146 answered knowledge-base questions (3 could not be judged: quota or provider errors).

### Judge: unfaithful or incorrect

- **uk-008** (incorrect) Do electric Northwinds need servicing at all?  
  → The answer omits the expected facts "2 years" and "36,000 miles," so it does not state the service interval.
- **uk-010** (unfaithful, incorrect) How much is a 5-year service plan for an Ion?  
  → The answer states £899, but the passage says the 5-year plan for Ion models is £699 (the £899 figure is for Aero).
- **uk-017** (incorrect) I'm deaf. How can I contact you?  
  → The answer does not mention the 18001 number or Sign Language, which are the expected facts for a deaf customer.
- **uk-018** (incorrect) My complaint to the dealer went nowhere. What now?  
  → The answer fails to provide the required escalation contact details (complaints@northwind-motors.example or 01632 960 000) for a complaint that went nowhere.
- **uk-021** (unfaithful) How long will I wait for a new Ion X after ordering?  
  → The cited passage [2] discusses Charge Plus tariffs and contains no information about delivery times, so the "10 to 16 weeks" claim is not supported by the cited passage.
- **uk-024** (unfaithful) What do I pay if I go over my mileage on a lease of an Ion?  
  → The answer claims Vela models are charged 15p per mile, but the passage states Vela is charged 12p per mile.
- **uk-032** (incorrect) Can I stop the car from sending my location to Northwind?  
  → The answer mentions only Offline mode and omits the expected fact that Limited mode is also an option.
- **us-004** (incorrect) Is maintenance free for the first few years?  
  → The answer fails to state the expected facts of 3 years and 36,000 miles, instead claiming it couldn't find information about maintenance-free periods.
- **us-013** (incorrect) Is my order deposit refundable?  
  → The answer omits the expected fact that the deposit is $1,000.
- **us-014** (incorrect) What's the monthly payment on an Ion 4 lease?  
  → The answer omits the required $3,999 due at signing fact.
- **de-019** (incorrect) Was kostet Connected Plus nach drei Jahren?  
  → The answer states 99 € pro Jahr but omits the expected fact of 9,90 € (per month).
- **dex-008** (incorrect) How do I complain if the dealer doesn't help?  
  → The answer omits the required contact details (+49 800 000 6000 or beschwerde@northwind-motors.example) for the Beschwerdemanagement.
- **mdl-002** (unfaithful) What's the EPA range of the Ion 4 Performance?  
  → The cited passage [3] does not state the EPA range of the Ion 4 Performance (it only discusses heat pump and winter range loss), so the 310-mile claim is not supported by the citation.
- **mdl-004** (unfaithful) Can I tow a caravan with the Ion X? How heavy?  
  → The answer incorrectly attributes the 1,000 kg braked towing limit (which belongs to the Ion 4 per passage [4]) to the Ion X, a claim not supported by the cited passages.
- **mdl-006** (unfaithful, incorrect) Does the Ion X have seven seats?  
  → The answer omits the expected fact that the seven seats are optional (via the 7 Seats Package), stating them as a standard feature.
- **mdl-008** (unfaithful) Can I use E10 petrol in the Aero?  
  → The answer states the expected facts (E10, approved, yes), but the claim that E10 is approved "in Europe" is not supported by the cited passage, which only states E10 is approved for the Aero without geographic qualification.
- **mdl-015** (incorrect) I got a flat tyre on my Ion 4. Is there a spare wheel?  
  → The answer omits the required speed limit of 80 km/h (50 mph) after using the repair kit.
- **kw-002** (incorrect) CBS service indicator  
  → The answer does not state that CBS stands for Condition Based Service, which is the required expected fact.
- **kw-009** (incorrect) FIN Zulassungsbescheinigung Feld E  
  → The answer omits the expected fact that the FIN is 17 digits long.
- **mkt-008** (incorrect) Can the Ion 4 tow a trailer?  
  → The answer fails to state that the Ion 4 is not approved for towing in Europe/UK (where it is approved up to 1,000 kg), only mentioning the U.S. restriction, so it does not fully convey the expected fact that the Ion 4 is not approved for towing.
- **mkt-009** (incorrect) Does the Vela support DC fast charging?  
  → The answer omits the expected fact that DC fast charging is not available on U.S. models (only Level 2 AC charging is supported there).
- **pub-004** (unfaithful) Which documents do I need to take my own car abroad?  
  → The answer is unfaithful because it cites passage [2] for the log book (V5C) and insurance certificate, but that specific claim is actually stated in passage [1], not [2].
- **fu-008** (incorrect) Does that apply to leases?  
  → The answer lists lease details but never states whether the referenced policy applies to leases (i.e., "not" or "only"), so it fails to answer the question.
- **fu-010** (unfaithful) What about the brake fluid?  
  → The cited passage does not state that the warranty covers brake fluid every 2 years, so the claim is unsupported.
- **md-001** (incorrect) If I lease an Ion 4, how long is the battery covered and how much is a home charger?  
  → The answer omits both expected facts: it never states the 8-year battery warranty duration nor the £999 home charger price.
- **md-003** (unfaithful, incorrect) What's the difference between the Ion 4 and Ion X in range and fast-charging power?  
  → The answer confuses motor power with fast-charging power (citing 250 kW and 400 kW as charging figures) and fails to state the expected 200 kW and 250 kW fast-charging values.

### Failures (deterministic checks)

- **uk-003** (missing fact; outcome `answer`, expected `kb`) My Ion 4 battery seems to be losing capacity. What does the warranty say?  
  → The Ion 4 battery warranty guarantees that the battery keeps at least 70% of its original usable capacity (state of health) during the 8-year or 100,000 miles period [2].
- **uk-008** (missing fact; outcome `answer`, expected `kb`) Do electric Northwinds need servicing at all?  
  → Northwind vehicles use Condition Based Service (CBS). Sensors monitor engine oil quality, brake pad wear and fluid condition, and the car calculates when each item needs attention based on how it is actually driven. The 
- **uk-010** (missing fact; outcome `answer`, expected `kb`) How much is a 5-year service plan for an Ion?  
  → For an Ion, a 5-year service plan costs £899 [1].
- **uk-017** (missing fact; outcome `answer`, expected `kb`) I'm deaf. How can I contact you?  
  → You can contact us in several ways [1, 4]:  *   Live chat: in the Northwind Connect app and at northwind-motors.example/uk/help, Monday to Saturday 8:00 to 22:00. *   Email: customer.care@northwind-motors.example. We rep
- **uk-018** (missing fact; outcome `answer`, expected `kb`) My complaint to the dealer went nowhere. What now?  
  → To proceed, you can either build your car using the online configurator at northwind-motors.example/uk/configure [1], talk to a retailer or order online [4], or book a service [2].
- **us-004** (missing fact; outcome `answer`, expected `kb`) Is maintenance free for the first few years?  
  → Let’s see what we can find out about maintenance for your Northwind Motors vehicle. [4] No oil changes are required for electric models. Tire rotation is recommended every 7,500 miles. An inspection service is due every 
- **us-013** (missing fact; outcome `answer`, expected `kb`) Is my order deposit refundable?  
  → Yes, your order deposit is fully refundable until you sign the purchase contract [2].
- **us-014** (missing fact; outcome `answer`, expected `kb`) What's the monthly payment on an Ion 4 lease?  
  → For an Ion 4 lease, the example provided shows a monthly payment of $499 [2].
- **de-019** (missing fact; outcome `answer`, expected `kb`) Was kostet Connected Plus nach drei Jahren?  
  → Nach drei Jahren kostet Connected Plus 99 € pro Jahr [1].
- **dex-008** (missing fact; outcome `answer`, expected `kb`) How do I complain if the dealer doesn't help?  
  → Here’s how to proceed if your dealer isn’t resolving your issue:  1.  Contact the Northwind Motors customer support team [3]. They will confirm receipt of your complaint and assign a personal contact. 2.  If the issue re
- **mdl-006** (missing fact; outcome `answer`, expected `kb`) Does the Ion X have seven seats?  
  → Yes, the Ion X has seven seats [1, 2].
- **mdl-015** (missing fact; outcome `answer`, expected `kb`) I got a flat tyre on my Ion 4. Is there a spare wheel?  
  → No, the Ion 4 does not have a spare wheel [1]. It comes with a tyre repair kit with sealant and an electric compressor stored under the boot floor.
- **kw-002** (missing fact; outcome `answer`, expected `kb`) CBS service indicator  
  → The CBS service indicator shows the next service due date and remaining mileage in the instrument cluster and in the Northwind Connect app [1].
- **kw-009** (missing fact; outcome `answer`, expected `kb`) FIN Zulassungsbescheinigung Feld E  
  → To find your FIN, it’s located in the first column of your vehicle registration certificate (Teil I), field E [1].
- **kw-011** (wrong route; outcome `refuse`, expected `kb`) LL-26 0W-20  
  → I'm sorry, I couldn't find that in our documentation. Would you like me to connect you with a member of our customer service team?
- **mkt-001** (wrong route; outcome `refuse`, expected `kb`) How long is the new vehicle warranty?  
  → I'm sorry, I couldn't find that in our documentation. Would you like me to connect you with a member of our customer service team?
- **mkt-009** (missing fact; outcome `answer`, expected `kb`) Does the Vela support DC fast charging?  
  → Yes, the Vela supports DC fast charging [1], [2]. In Europe and the UK, it can use DC chargers at up to 50 kW, charging from 10 to 80% in about 25 minutes.
- **pub-005** (wrong route; outcome `refuse`, expected `kb`) Do I need an international driving permit?  
  → I'm sorry, I couldn't find that in our documentation. Would you like me to connect you with a member of our customer service team?
- **pub-006** (wrong route; outcome `refuse`, expected `kb`) Is there an extra vehicle tax for expensive electric cars?  
  → I'm sorry, I couldn't find that in our documentation. Would you like me to connect you with a member of our customer service team?
- **fu-005** (wrong route; outcome `refuse`, expected `kb`) Does it work in Spain too?  
  → I'm sorry, I couldn't find that in our documentation. Would you like me to connect you with a member of our customer service team?
- **fu-008** (missing fact; outcome `answer`, expected `kb`) Does that apply to leases?  
  → Regarding leases, we offer lease terms of 24, 36 or 39 months [1]. Annual mileage options are 7,500, 10,000, 12,000 or 15,000 miles [1]. An excess mileage charge of $0.25 per mile applies [1]. At lease end, you can retur
- **md-001** (missing fact; outcome `answer`, expected `kb`) If I lease an Ion 4, how long is the battery covered and how much is a home charger?  
  → Every new Ion 4 and Ion X includes 12 months of Charge Plus free of charge [1]. The high-voltage battery is covered by the high-voltage battery warranty [4].
- **md-002** (wrong route; outcome `refuse`, expected `kb`) What's included for free with a new Ion: maintenance, charging and roadside help?  
  → I'm sorry, I couldn't find that in our documentation. Would you like me to connect you with a member of our customer service team?
- **md-003** (missing fact; outcome `answer`, expected `kb`) What's the difference between the Ion 4 and Ion X in range and fast-charging power?  
  → Okay, let’s look at the range and fast-charging power for the Ion 4 and Ion X.  The Ion 4 has a WLTP range of 610 km (379 miles) and an EPA range of 340 miles [1]. The Ion X has a WLTP range of 580 km (360 miles) and an 
- **pii-004** (wrong route; outcome `handoff`, expected `kb`) Call me back on +44 7700 900456 about the hotline opening hours on Saturday.  
  → I'll connect you with a member of our customer service team. They will see this conversation, so you won't need to repeat yourself.
