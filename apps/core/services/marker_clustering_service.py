"""
Advanced Marker Clustering Service
Enterprise-grade marker clustering for high-density Google Maps visualizations.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from math import sqrt, sin, cos, radians, atan2
from django.conf import settings
from django.core.cache import cache
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


@dataclass
class MarkerData:
    """Data structure for marker information."""
    id: str
    lat: float
    lng: float
    title: str
    icon: Optional[str] = None
    data: Optional[Dict] = None


@dataclass
class ClusterConfig:
    """Configuration for clustering behavior."""
    grid_size: int = 60
    max_zoom_for_clustering: int = 15
    minimum_cluster_size: int = 2
    enable_spiderfier: bool = True
    animation_duration: int = 300
    cluster_radius_pixels: int = 40


class AdvancedMarkerClusteringService:
    """
    Advanced marker clustering service with intelligent algorithms and performance optimization.
    """

    def __init__(self):
        self.cache_key_prefix = "marker_cluster"
        self.cache_ttl = 3600  # 1 hour

    def generate_cluster_configuration(self, view_type: str = 'default') -> Dict[str, Any]:
        """
        Generate clustering configuration optimized for different view types.

        Args:
            view_type: Type of view ('asset', 'checkpoint', 'vendor', 'default')

        Returns:
            Dictionary containing clustering configuration
        """
        base_config = {
            'enabled': True,
            'gridSize': 60,
            'maxZoom': 15,
            'minimumClusterSize': 2,
            'averageCenter': True,
            'ignoreHidden': True,
            'enableRetinaIcons': True,
            'calculator': self._get_cluster_calculator(),
            'clusterClass': 'marker-cluster',
            'styles': self._get_cluster_styles(view_type),
            'spiderfier': {
                'enabled': True,
                'keepSpiderfied': False,
                'nearbyDistance': 50,
                'circleSpiralSwitchover': 9,
                'circleFootSeparation': 25,
                'circleStartAngle': 0,
                'spiralFootSeparation': 30,
                'spiralLengthStart': 15,
                'spiralLengthFactor': 5,
                'legWeight': 2,
                'legColors': ['#007bff', '#28a745', '#ffc107', '#dc3545']
            }
        }

        # Customize based on view type
        if view_type == 'asset':
            base_config.update({
                'gridSize': 80,  # Larger clusters for assets
                'minimumClusterSize': 3,
                'maxZoom': 16,
            })
        elif view_type == 'checkpoint':
            base_config.update({
                'gridSize': 40,  # Smaller clusters for precise checkpoint locations
                'minimumClusterSize': 2,
                'maxZoom': 18,
            })
        elif view_type == 'vendor':
            base_config.update({
                'gridSize': 70,  # Medium clusters for vendor locations
                'minimumClusterSize': 2,
                'maxZoom': 15,
            })

        return base_config

    def _get_cluster_calculator(self) -> str:
        """Return JavaScript function for calculating cluster sizes."""
        return """
        function(markers, numStyles) {
            var count = markers.length;
            var index = 0;

            // Determine cluster size category
            if (count < 10) {
                index = 0;
            } else if (count < 25) {
                index = 1;
            } else if (count < 50) {
                index = 2;
            } else if (count < 100) {
                index = 3;
            } else {
                index = 4;
            }

            // Ensure index doesn't exceed available styles
            index = Math.min(index, numStyles - 1);

            return {
                text: count.toString(),
                index: index,
                title: count + ' items in this cluster'
            };
        }
        """

    def _get_cluster_styles(self, view_type: str) -> List[Dict[str, Any]]:
        """
        Generate cluster styles optimized for different view types.

        Args:
            view_type: Type of view for style optimization

        Returns:
            List of cluster style definitions
        """
        # Base color schemes for different view types
        color_schemes = {
            'asset': ['#007bff', '#0056b3', '#004085', '#003766', '#002447'],  # Blue shades
            'checkpoint': ['#28a745', '#1e7e34', '#155724', '#0f4c1e', '#0a3d19'],  # Green shades
            'vendor': ['#ffc107', '#e0a800', '#d39e00', '#b8860b', '#996f00'],  # Amber shades
            'default': ['#6c757d', '#5a6268', '#495057', '#343a40', '#212529'],  # Gray shades
        }

        colors = color_schemes.get(view_type, color_schemes['default'])

        styles = []
        sizes = [40, 50, 60, 70, 80]  # Cluster sizes

        for i, (color, size) in enumerate(zip(colors, sizes)):
            styles.append({
                'url': f'/static/images/maps/clusters/{view_type}_cluster_{i+1}.svg',
                'width': size,
                'height': size,
                'anchorText': [int(size/2), int(size/2)],
                'anchorIcon': [int(size/2), int(size/2)],
                'textColor': '#ffffff',
                'textSize': 11 + i,
                'fontFamily': "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
                'fontWeight': '600',
                'backgroundPosition': 'center center',
                'className': f'cluster-{view_type}-{i+1}',
                'zIndex': 10000 + i
            })

        return styles

    def process_markers_for_clustering(self, markers: List[Dict[str, Any]],
                                     view_type: str = 'default',
                                     bounds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Process markers for optimal clustering performance.

        Args:
            markers: List of marker data
            view_type: Type of view for optimization
            bounds: Optional map bounds for filtering

        Returns:
            Processed clustering data with performance optimizations
        """
        try:
            # Create cache key
            cache_key = f"{self.cache_key_prefix}:{view_type}:{len(markers)}"
            if bounds:
                bounds_str = f"{bounds['north']:.4f},{bounds['south']:.4f},{bounds['east']:.4f},{bounds['west']:.4f}"
                cache_key += f":{bounds_str}"

            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Clustering cache hit for {len(markers)} markers")
                return cached_result

            # Filter markers by bounds if provided
            if bounds:
                markers = self._filter_markers_by_bounds(markers, bounds)

            # Pre-process markers for clustering optimization
            processed_markers = []
            for marker in markers:
                processed_marker = {
                    'id': marker.get('id', ''),
                    'position': {
                        'lat': float(marker.get('lat', 0)),
                        'lng': float(marker.get('lng', 0))
                    },
                    'title': marker.get('title', ''),
                    'icon': marker.get('icon'),
                    'data': marker.get('data', {}),
                    'cluster_weight': self._calculate_marker_weight(marker, view_type)
                }
                processed_markers.append(processed_marker)

            # Generate clustering configuration
            cluster_config = self.generate_cluster_configuration(view_type)

            # Performance optimizations
            performance_config = self._generate_performance_config(len(processed_markers))

            result = {
                'markers': processed_markers,
                'clustering': cluster_config,
                'performance': performance_config,
                'view_type': view_type,
                'total_markers': len(processed_markers),
                'optimization_applied': True,
                'cache_duration': self.cache_ttl
            }

            # Cache the result
            cache.set(cache_key, result, self.cache_ttl)
            logger.info(f"Processed {len(processed_markers)} markers for {view_type} clustering")

            return result

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Failed to process markers for clustering: {str(e)}", exc_info=True)
            return {
                'markers': markers,
                'clustering': self.generate_cluster_configuration('default'),
                'performance': {'error': str(e)},
                'optimization_applied': False
            }

    def _filter_markers_by_bounds(self, markers: List[Dict[str, Any]],
                                bounds: Dict[str, float]) -> List[Dict[str, Any]]:
        """Filter markers within map bounds for performance."""
        filtered = []
        for marker in markers:
            lat = float(marker.get('lat', 0))
            lng = float(marker.get('lng', 0))

            if (bounds['south'] <= lat <= bounds['north'] and
                bounds['west'] <= lng <= bounds['east']):
                filtered.append(marker)

        return filtered

    def _calculate_marker_weight(self, marker: Dict[str, Any], view_type: str) -> int:
        """Calculate marker weight for clustering priority."""
        weight = 1  # Base weight

        # Adjust weight based on marker importance
        data = marker.get('data', {})

        if view_type == 'asset':
            # Critical assets have higher weight
            if data.get('status') == 'critical':
                weight += 3
            elif data.get('status') == 'warning':
                weight += 2

        elif view_type == 'checkpoint':
            # Mandatory checkpoints have higher weight
            if data.get('mandatory', False):
                weight += 2

        elif view_type == 'vendor':
            # Preferred vendors have higher weight
            if data.get('preferred', False):
                weight += 2

        return weight

    def _generate_performance_config(self, marker_count: int) -> Dict[str, Any]:
        """Generate performance configuration based on marker count."""
        config = {
            'lazy_loading': marker_count > 100,
            'batch_size': min(50, max(10, marker_count // 10)),
            'animation_enabled': marker_count < 200,
            'detailed_tooltips': marker_count < 500,
            'real_time_updates': marker_count < 1000,
        }

        # Performance recommendations
        if marker_count > 1000:
            config['recommendations'] = [
                'Consider server-side clustering',
                'Implement viewport-based loading',
                'Use simplified marker icons'
            ]
        elif marker_count > 500:
            config['recommendations'] = [
                'Enable lazy loading',
                'Reduce cluster animation'
            ]

        return config

    def generate_clustering_javascript(self, view_type: str = 'default') -> str:
        """
        Generate optimized JavaScript for marker clustering.

        Args:
            view_type: Type of view for JavaScript optimization

        Returns:
            JavaScript code for advanced clustering
        """
        config = self.generate_cluster_configuration(view_type)

        js_code = f"""
// Advanced Marker Clustering for {view_type.title()} View
class AdvancedMarkerCluster {{
    constructor(map, markers, options = {{}}) {{
        this.map = map;
        this.markers = markers || [];
        this.options = Object.assign({json.dumps(config, indent=8)}, options);

        this.markerCluster = null;
        this.spiderfier = null;
        this.activeInfoWindow = null;

        this.initializeCluster();
        if (this.options.spiderfier.enabled) {{
            this.initializeSpiderfier();
        }}
    }}

    initializeCluster() {{
        // Load MarkerClusterer library if not already loaded
        if (typeof MarkerClusterer === 'undefined') {{
            this.loadClusterLibrary().then(() => {{
                this.createCluster();
            }});
        }} else {{
            this.createCluster();
        }}
    }}

    async loadClusterLibrary() {{
        return new Promise((resolve, reject) => {{
            const script = document.createElement('script');
            script.src = 'https://developers.google.com/maps/documentation/javascript/examples/markerclusterer/markerclusterer.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        }});
    }}

    createCluster() {{
        const clusterOptions = {{
            gridSize: this.options.gridSize,
            maxZoom: this.options.maxZoom,
            minimumClusterSize: this.options.minimumClusterSize,
            averageCenter: this.options.averageCenter,
            ignoreHidden: this.options.ignoreHidden,
            enableRetinaIcons: this.options.enableRetinaIcons,
            styles: this.options.styles,
            calculator: {self._get_cluster_calculator()}
        }};

        this.markerCluster = new MarkerClusterer(this.map, this.markers, clusterOptions);

        // Add cluster click listener for zoom behavior
        google.maps.event.addListener(this.markerCluster, 'clusterclick', (cluster) => {{
            const map = this.map;
            const currentZoom = map.getZoom();
            const maxZoom = this.options.maxZoom;

            if (currentZoom < maxZoom) {{
                map.fitBounds(cluster.getBounds());
                if (map.getZoom() > maxZoom) {{
                    map.setZoom(maxZoom);
                }}
            }} else {{
                // Show cluster details at max zoom
                this.showClusterDetails(cluster);
            }}
        }});

        console.log(`Advanced clustering initialized for {view_type} with ${{this.markers.length}} markers`);
    }}

    initializeSpiderfier() {{
        // Initialize Overlapping Marker Spiderfier if available
        if (typeof OverlappingMarkerSpiderfier !== 'undefined') {{
            const spiderConfig = this.options.spiderfier;

            this.spiderfier = new OverlappingMarkerSpiderfier(this.map, {{
                keepSpiderfied: spiderConfig.keepSpiderfied,
                nearbyDistance: spiderConfig.nearbyDistance,
                circleSpiralSwitchover: spiderConfig.circleSpiralSwitchover,
                circleFootSeparation: spiderConfig.circleFootSeparation,
                circleStartAngle: spiderConfig.circleStartAngle,
                spiralFootSeparation: spiderConfig.spiralFootSeparation,
                spiralLengthStart: spiderConfig.spiralLengthStart,
                spiralLengthFactor: spiderConfig.spiralLengthFactor,
                legWeight: spiderConfig.legWeight
            }});

            // Add markers to spiderfier
            this.markers.forEach(marker => {{
                this.spiderfier.addMarker(marker);
            }});

            // Set up spiderfier event listeners
            this.spiderfier.addListener('click', (marker, event) => {{
                this.showMarkerInfo(marker);
            }});

            this.spiderfier.addListener('spiderfy', (markers) => {{
                this.closeInfoWindow();
            }});
        }}
    }}

    showClusterDetails(cluster) {{
        const markers = cluster.getMarkers();
        const center = cluster.getCenter();

        const content = `
            <div class="cluster-info-window">
                <h6><i class="fas fa-layer-group me-2"></i>Cluster Details</h6>
                <p><strong>${{markers.length}}</strong> items in this area</p>
                <div class="cluster-actions">
                    <button class="btn btn-sm btn-primary" onclick="window.clusterManager.expandCluster('${{cluster.id}}')">
                        <i class="fas fa-expand me-1"></i> Expand
                    </button>
                    <button class="btn btn-sm btn-outline-info" onclick="window.clusterManager.listClusterItems('${{cluster.id}}')">
                        <i class="fas fa-list me-1"></i> List Items
                    </button>
                </div>
            </div>
        `;

        this.showInfoWindow(content, center);
    }}

    showMarkerInfo(marker) {{
        const content = this.generateMarkerContent(marker);
        this.showInfoWindow(content, marker.getPosition());
    }}

    generateMarkerContent(marker) {{
        const data = marker.data || {{}};
        return `
            <div class="marker-info-window">
                <h6>${{marker.getTitle() || 'Location Details'}}</h6>
                <div class="marker-details">
                    ${{this.formatMarkerData(data)}}
                </div>
                <div class="marker-actions mt-2">
                    <button class="btn btn-sm btn-outline-primary" onclick="window.showLocationDetails('${{marker.id}}')">
                        <i class="fas fa-info-circle me-1"></i> Details
                    </button>
                    <button class="btn btn-sm btn-outline-success" onclick="window.navigateToLocation(${{marker.getPosition().lat()}}, ${{marker.getPosition().lng()}})">
                        <i class="fas fa-directions me-1"></i> Navigate
                    </button>
                </div>
            </div>
        `;
    }}

    formatMarkerData(data) {{
        let html = '';
        for (const [key, value] of Object.entries(data)) {{
            if (key !== 'id' && value) {{
                const displayKey = key.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase());
                html += `<div class="data-item"><strong>${{displayKey}}:</strong> ${{value}}</div>`;
            }}
        }}
        return html || '<div class="text-muted">No additional details available</div>';
    }}

    showInfoWindow(content, position) {{
        this.closeInfoWindow();

        this.activeInfoWindow = new google.maps.InfoWindow({{
            content: content,
            position: position
        }});

        this.activeInfoWindow.open(this.map);
    }}

    closeInfoWindow() {{
        if (this.activeInfoWindow) {{
            this.activeInfoWindow.close();
            this.activeInfoWindow = null;
        }}
    }}

    // Public methods for cluster management
    addMarker(marker) {{
        this.markers.push(marker);
        if (this.markerCluster) {{
            this.markerCluster.addMarker(marker);
        }}
        if (this.spiderfier) {{
            this.spiderfier.addMarker(marker);
        }}
    }}

    removeMarker(marker) {{
        const index = this.markers.indexOf(marker);
        if (index > -1) {{
            this.markers.splice(index, 1);
        }}
        if (this.markerCluster) {{
            this.markerCluster.removeMarker(marker);
        }}
        if (this.spiderfier) {{
            this.spiderfier.removeMarker(marker);
        }}
    }}

    clearMarkers() {{
        if (this.markerCluster) {{
            this.markerCluster.clearMarkers();
        }}
        if (this.spiderfier) {{
            this.spiderfier.clearMarkers();
        }}
        this.markers = [];
        this.closeInfoWindow();
    }}

    refresh() {{
        if (this.markerCluster) {{
            this.markerCluster.repaint();
        }}
    }}
}}

// Global cluster manager instance
window.AdvancedMarkerCluster = AdvancedMarkerCluster;
"""

        return mark_safe(js_code)

    def clear_clustering_cache(self, view_type: Optional[str] = None):
        """Clear clustering cache for specific view type or all."""
        if view_type:
            pattern = f"{self.cache_key_prefix}:{view_type}:*"
        else:
            pattern = f"{self.cache_key_prefix}:*"

        # Note: This is a simplified cache clearing approach
        # In production, implement proper cache key pattern matching
        logger.info(f"Clearing clustering cache for pattern: {pattern}")


# Global service instance
marker_clustering_service = AdvancedMarkerClusteringService()