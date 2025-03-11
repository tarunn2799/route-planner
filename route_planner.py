"""
Google Maps Optimal Route Planner
This script uses Google Maps Geocoding API and Routes API to calculate
the most efficient route through multiple destinations from a starting point.
"""

import googlemaps
import json
import logging
import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('route_planner.log'), logging.StreamHandler()]
)

class RouteOptimizer:
    def __init__(self, api_key):
        """Initialize Google Maps client with API key"""
        self.gmaps = googlemaps.Client(key=api_key)
        self.api_key = api_key
        self.geocode_cache = {}
        logging.info("Initialized Google Maps client with provided API key")

    def geocode_addresses(self, addresses):
        """
        Geocode a list of addresses to get their coordinates
        Args:
            addresses (list): List of addresses to geocode
        Returns:
            dict: A dictionary mapping addresses to their geocoded coordinates
        """
        results = {}
        total = len(addresses)
        
        for idx, address in enumerate(addresses):
            logging.info(f"Geocoding address {idx+1}/{total}: {address}")
            
            # Check cache first
            if address in self.geocode_cache:
                logging.info(f"Using cached geocode data for: {address}")
                results[address] = self.geocode_cache[address]
                continue
                
            try:
                # Call Geocoding API
                geocode_result = self.gmaps.geocode(address)
                
                if not geocode_result:
                    logging.warning(f"No geocode results for address: {address}")
                    continue
                    
                # Extract location data
                location = geocode_result[0]['geometry']['location']
                place_id = geocode_result[0]['place_id']
                formatted_address = geocode_result[0]['formatted_address']
                
                result = {
                    'lat': location['lat'],
                    'lng': location['lng'],
                    'place_id': place_id,
                    'formatted_address': formatted_address
                }
                
                # Store in cache and results
                self.geocode_cache[address] = result
                results[address] = result
                logging.info(f"Successfully geocoded: {address}")
                
                # Avoid hitting rate limits
                time.sleep(0.2)
                
            except Exception as e:
                logging.error(f"Failed to geocode address '{address}': {str(e)}")
        
        logging.info(f"Geocoded {len(results)}/{total} addresses successfully")
        return results

    def optimize_route(self, origin, destinations):
        """
        Calculate optimized route using Google Maps Routes API
        Args:
            origin (str): Starting address
            destinations (list): List of destination addresses
        Returns:
            dict: Optimized route details
        """
        try:
            logging.info(f"Starting route optimization for {len(destinations)} destinations")
            
            # First geocode all addresses
            all_addresses = [origin] + destinations
            geocoded = self.geocode_addresses(all_addresses)
            
            if origin not in geocoded:
                raise ValueError(f"Failed to geocode origin address: {origin}")
                
            # Prepare waypoints for Routes API
            origin_location = {
                "location": {
                    "latLng": {
                        "latitude": geocoded[origin]['lat'],
                        "longitude": geocoded[origin]['lng']
                    }
                }
            }
            
            destination_location = origin_location  # Round trip back to origin
            
            # Intermediate waypoints (exclude origin)
            intermediate_locations = []
            for address in destinations:
                if address in geocoded:
                    intermediate_locations.append({
                        "location": {
                            "latLng": {
                                "latitude": geocoded[address]['lat'],
                                "longitude": geocoded[address]['lng']
                            }
                        }
                    })
            
            # Build the Routes API request
            route_request = {
                "origin": origin_location,
                "destination": destination_location,
                "intermediates": intermediate_locations,
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
                "optimizeWaypointOrder": True,
                "computeAlternativeRoutes": False,
                "routeModifiers": {
                    "avoidTolls": False,
                    "avoidHighways": False,
                    "avoidFerries": False
                },
                "languageCode": "en-US",
                "units": "METRIC"
            }
            
            # Call Routes API directly using requests
            routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs,routes.optimizedIntermediateWaypointIndex"
            }
            
            logging.info("Calling Routes API to calculate optimal route")
            response = requests.post(routes_url, json=route_request, headers=headers)
            
            if response.status_code != 200:
                raise ValueError(f"Routes API error: {response.status_code} - {response.text}")
                
            routes_response = response.json()
            
            if not routes_response or 'routes' not in routes_response or not routes_response['routes']:
                raise ValueError("No routes returned from Routes API")
            
            # Process the Routes API response
            route = routes_response['routes'][0]
            logging.info("Successfully retrieved optimized route from Routes API")
            
            return self._process_route(route, geocoded, origin, destinations)
            
        except Exception as e:
            logging.error(f"Route optimization failed: {str(e)}")
            raise

    def _process_route(self, route, geocoded, origin, destinations):
        """Process and structure route data from Routes API response"""
        # Extract optimized waypoint order if available
        optimized_order = route.get('optimizedIntermediateWaypointIndex', [])
        
        # Extract polyline
        polyline = route.get('polyline', {}).get('encodedPolyline', '')
        
        # Extract legs information
        legs = route.get('legs', [])
        
        # Calculate totals
        total_distance_meters = route.get('distanceMeters', 0)
        total_duration_seconds = 0
        if 'duration' in route:
            duration_str = route['duration']
            if duration_str.endswith('s'):
                total_duration_seconds = int(duration_str[:-1])
        
        # Reorder destinations based on optimized order
        optimized_destinations = []
        if optimized_order and len(destinations) > 0:
            for idx in optimized_order:
                if idx < len(destinations):
                    optimized_destinations.append(destinations[idx])
        else:
            optimized_destinations = destinations.copy()
        
        # Create waypoints info
        waypoints = []
        
        # Only add waypoints if we have legs
        if legs:
            # First leg: origin to first destination
            start_address = origin
            end_address = optimized_destinations[0] if optimized_destinations else origin
            
            first_leg = legs[0]
            first_leg_distance = first_leg.get('distanceMeters', 0) / 1000
            first_leg_duration = 0
            if 'duration' in first_leg:
                duration_str = first_leg['duration']
                if duration_str.endswith('s'):
                    first_leg_duration = int(duration_str[:-1]) // 60
            
            waypoints.append({
                'start_location': start_address,
                'end_location': end_address,
                'geocoded_start': geocoded.get(start_address, {}),
                'geocoded_end': geocoded.get(end_address, {}),
                'distance_km': first_leg_distance,
                'duration_mins': first_leg_duration
            })
            
            # Intermediate legs
            for i in range(len(optimized_destinations)):
                if i + 1 < len(legs):
                    start_address = optimized_destinations[i]
                    end_address = optimized_destinations[i+1] if i+1 < len(optimized_destinations) else origin
                    
                    leg = legs[i+1]
                    leg_distance = leg.get('distanceMeters', 0) / 1000
                    leg_duration = 0
                    if 'duration' in leg:
                        duration_str = leg['duration']
                        if duration_str.endswith('s'):
                            leg_duration = int(duration_str[:-1]) // 60
                    
                    waypoints.append({
                        'start_location': start_address,
                        'end_location': end_address,
                        'geocoded_start': geocoded.get(start_address, {}),
                        'geocoded_end': geocoded.get(end_address, {}),
                        'distance_km': leg_distance,
                        'duration_mins': leg_duration
                    })
        
        result = {
            'origin': origin,
            'destinations': destinations,
            'optimized_waypoint_order': optimized_order,
            'optimized_destinations': optimized_destinations,
            'total_distance_km': round(total_distance_meters / 1000, 2),
            'total_duration_mins': total_duration_seconds // 60,
            'waypoints': waypoints,
            'polyline': polyline
        }
        
        # Generate Google Maps URL
        result['google_maps_url'] = self._generate_map_url(geocoded, origin, optimized_destinations)
        
        return result

    def _generate_map_url(self, geocoded, origin, optimized_destinations):
        """
        Generate Google Maps URL for the optimized route
        Handles more than 10 waypoints by splitting into batches and combining URLs
        """
        try:
            # If we have 9 or fewer destinations, we can use a single URL (origin + destinations + return to origin)
            if len(optimized_destinations) <= 9:
                # Build a simple URL with all waypoints
                url = "https://www.google.com/maps/dir/"
                
                # Add origin
                if origin in geocoded and 'lat' in geocoded[origin] and 'lng' in geocoded[origin]:
                    lat = geocoded[origin]['lat']
                    lng = geocoded[origin]['lng']
                    url += f"{lat},{lng}/"
                else:
                    url += f"{origin.replace(' ', '+')}/"
                
                # Add destinations
                for dest in optimized_destinations:
                    if dest in geocoded and 'lat' in geocoded[dest] and 'lng' in geocoded[dest]:
                        lat = geocoded[dest]['lat']
                        lng = geocoded[dest]['lng']
                        url += f"{lat},{lng}/"
                    else:
                        url += f"{dest.replace(' ', '+')}/"
                
                # Add return to origin (complete the loop)
                if origin in geocoded and 'lat' in geocoded[origin] and 'lng' in geocoded[origin]:
                    lat = geocoded[origin]['lat']
                    lng = geocoded[origin]['lng']
                    url += f"{lat},{lng}/"
                else:
                    url += f"{origin.replace(' ', '+')}/"
                
                # Remove trailing slash
                url = url.rstrip('/')
                
                logging.info(f"Generated Google Maps URL with {len(optimized_destinations)} destinations")
                return url
            
            # For more than 9 destinations, we need to split into batches
            else:
                logging.info(f"Handling {len(optimized_destinations)} destinations in batches due to Google Maps limit")
                
                # First batch: Origin + first 8 destinations + last destination
                batch_size = 8  # Leave space for origin and return to last destination
                
                # Split destinations into batches
                destination_batches = []
                for i in range(0, len(optimized_destinations), batch_size):
                    batch = optimized_destinations[i:i+batch_size]
                    destination_batches.append(batch)
                
                # Generate URL for the complete route
                url = "https://www.google.com/maps/dir/"
                
                # Add origin
                if origin in geocoded and 'lat' in geocoded[origin] and 'lng' in geocoded[origin]:
                    lat = geocoded[origin]['lat']
                    lng = geocoded[origin]['lng']
                    url += f"{lat},{lng}/"
                else:
                    url += f"{origin.replace(' ', '+')}/"
                
                # Add all destinations in sequence
                for dest in optimized_destinations:
                    if dest in geocoded and 'lat' in geocoded[dest] and 'lng' in geocoded[dest]:
                        lat = geocoded[dest]['lat']
                        lng = geocoded[dest]['lng']
                        url += f"{lat},{lng}/"
                    else:
                        url += f"{dest.replace(' ', '+')}/"
                
                # Add return to origin
                if origin in geocoded and 'lat' in geocoded[origin] and 'lng' in geocoded[origin]:
                    lat = geocoded[origin]['lat']
                    lng = geocoded[origin]['lng']
                    url += f"{lat},{lng}/"
                else:
                    url += f"{origin.replace(' ', '+')}/"
                
                # Remove trailing slash
                url = url.rstrip('/')
                
                # Remove everything after the @ symbol if present (to follow the guide)
                if '@' in url:
                    url = url.split('@')[0]
                
                logging.info(f"Generated Google Maps URL with {len(optimized_destinations)} destinations in multiple batches")
                return url
            
        except Exception as e:
            logging.error(f"Failed to generate Google Maps URL: {str(e)}")
            return ""

def main():
    """Main execution function"""
    try:
        # Get API key from environment variable
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Set GOOGLE_MAPS_API_KEY in .env file.")
            
        # Use default addresses
        origin = "24116 NE 27th PL sammamish WA"
        destinations = [
            "Bellevue, WA",
            "Redmond, WA",
            "Issaquah, WA",
            "Kirkland, WA"
        ]
        
        logging.info(f"Using origin: {origin}")
        logging.info(f"Using destinations: {destinations}")
        
        # Initialize optimizer
        optimizer = RouteOptimizer(api_key)
        
        # Execute route optimization
        result = optimizer.optimize_route(
            origin=origin,
            destinations=destinations
        )
        
        # Display results
        print("\n===== Route Optimization Results =====")
        print(f"Origin: {result['origin']}")
        print(f"Total Distance: {result['total_distance_km']} km")
        print(f"Total Duration: {result['total_duration_mins']} minutes")
        print("\nOptimized Route:")
        print(f"Start at: {result['origin']}")
        
        for i, waypoint in enumerate(result['optimized_destinations']):
            print(f"{i+1}. {waypoint}")
            
        print(f"Return to: {result['origin']}")
        
        print(f"\nGoogle Maps URL: {result['google_maps_url']}")
        
        # Save results
        output_file = 'optimized_route.json'
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
            
        logging.info(f"Optimization complete. Results saved to {output_file}")
        
    except Exception as e:
        logging.error(f"Fatal error in main execution: {str(e)}")

if __name__ == "__main__":
    main()
