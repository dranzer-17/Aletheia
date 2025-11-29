"""Geocoding utility to convert lat/long to location information."""

from __future__ import annotations

from typing import Optional, Dict
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

from logger import get_logger

logger = get_logger(__name__)

# Initialize geocoder with a user agent
_geocoder = None


def get_geocoder():
    """Get or create the geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(user_agent="globee-news-app/1.0")
    return _geocoder


def reverse_geocode(latitude: float, longitude: float) -> Dict[str, Optional[str]]:
    """
    Reverse geocode lat/long to get city, state, and country information.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    
    Returns:
        Dictionary with 'city', 'state', 'country', and 'country_code' keys.
        Values may be None if not found.
    """
    geocoder = get_geocoder()
    
    try:
        # Add a small delay to respect rate limits
        time.sleep(1)
        
        location = geocoder.reverse((latitude, longitude), exactly_one=True, timeout=10)
        
        if not location:
            logger.warning(f"No location found for coordinates: {latitude}, {longitude}")
            return {
                "city": None,
                "state": None,
                "country": None,
                "country_code": None,
            }
        
        address = location.raw.get("address", {})
        
        # Extract city (try multiple possible keys)
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("city_district")
        )
        
        # Extract state (try multiple possible keys)
        state = (
            address.get("state")
            or address.get("region")
            or address.get("province")
            or address.get("state_district")
        )
        
        # Extract country
        country = address.get("country")
        
        # Extract country code (ISO 3166-1 alpha-2)
        country_code = address.get("country_code", "").upper() if address.get("country_code") else None
        
        result = {
            "city": city,
            "state": state,
            "country": country,
            "country_code": country_code,
        }
        
        logger.info(
            f"Geocoded {latitude}, {longitude} -> City: {city}, State: {state}, Country: {country} ({country_code})"
        )
        
        return result
        
    except GeocoderTimedOut:
        logger.error(f"Geocoding timeout for coordinates: {latitude}, {longitude}")
        return {
            "city": None,
            "state": None,
            "country": None,
            "country_code": None,
        }
    except GeocoderServiceError as e:
        logger.error(f"Geocoding service error: {e}")
        return {
            "city": None,
            "state": None,
            "country": None,
            "country_code": None,
        }
    except Exception as e:
        logger.error(f"Unexpected error during geocoding: {e}", exc_info=True)
        return {
            "city": None,
            "state": None,
            "country": None,
            "country_code": None,
        }

