"""
Unified safety zones processor module.

This module exposes the enhanced safety processor as the default and only
implementation for handling flight-route safety computations. Legacy fallback
implementations have been removed – the application now always relies on the
enhanced processor.
"""

# Re-export the EnhancedSafetyProcessor defined in safety_enhanced so that the
# rest of the codebase can simply import it from orbit.planners.safety_zones.

from .safety_enhanced import EnhancedSafetyProcessor

__all__ = ["EnhancedSafetyProcessor"]
