# Example Use Cases & Solutions

### Booking agent confirms a room while Research agent is still comparing options.

**Problem:** Race condition in travel planning workflow  
**Solution:** Use event-driven coordination to ensure proper sequencing

```python
@coordinate("hotel_researcher")
def research_hotels(destination, dates):
    hotels = search_hotels(destination, dates)
    best_hotel = analyze_options(hotels)
    return best_hotel  # @coordinate automatically puts this in event_data['result']

@when("hotel_researcher_complete")  # Auto-triggered when research_hotels() completes
def start_booking(event_data):
    selected_hotel = event_data['result']  # Gets the return value from research_hotels()
    booking_agent(selected_hotel)

# Option 1: Without @coordinate (minimal - just does the work)
def booking_agent(hotel):
    return book_hotel(hotel)

# Option 2: With @coordinate (adds monitoring + events for booking step)
# @coordinate("hotel_booker")
# def booking_agent(hotel):
#     return book_hotel(hotel)  # Also emits hotel_booker_started/complete events
```

### Data analysis started before data collection finished

**Problem:** Analyzer working with incomplete data  
**Solution:** Event-driven pipeline coordination

```python
@coordinate("data_collector")
def collect_customer_data():
    data = scrape_multiple_sources()
    emit("data_collection_complete", {"dataset": data})
    return data

@when("data_collection_complete")
def start_analysis(event_data):
    dataset = event_data['dataset']
    analysis_agent(dataset)  # Only starts when collection is done

@coordinate("data_analyzer")
def analysis_agent(dataset):
    return perform_analysis(dataset)
```

### Multiple agents hitting OpenAI rate limits and failing

**Problem:** Several research agents calling OpenAI API simultaneously, exceeding rate limits  
**Solution:** Use API resource lock to queue requests safely

```python
@coordinate("market_researcher", lock_name="openai_api")
def research_market_trends(industry):
    # Only one agent can call OpenAI API at a time
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Research {industry} trends"}]
    )
    return response

@coordinate("competitor_researcher", lock_name="openai_api")
def research_competitors(company):
    # Waits for market_researcher to finish before making API call
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Analyze {company} competitors"}]
    )
    return response
```

### Multiple agents updating the same customer record

**Problem:** Database corruption from concurrent updates  
**Solution:** Lock per customer during updates

```python
@coordinate("profile_updater", lock_name="customer_456")
def update_profile(customer_id, new_data):
    # Only one agent can update this customer at a time
    return db.update_customer(customer_id, new_data)

@coordinate("preference_updater", lock_name="customer_456")
def update_preferences(customer_id, preferences):
    # Waits for profile update to complete
    return db.update_preferences(customer_id, preferences)
```
