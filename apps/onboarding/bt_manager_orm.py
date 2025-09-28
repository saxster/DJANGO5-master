"""
Django ORM conversions for BtManager complex queries.
Replaces PostgreSQL functions for Business Territory (BT) hierarchy traversal.
"""

from typing import List, Dict, Any, Union, Optional


class BtManagerORM:
    """Django ORM implementations for complex BT hierarchy queries"""
    
    @staticmethod
    def get_bulist(
        bu_id: int,
        include_parents: bool = True,
        include_children: bool = True,
        return_type: str = 'array',
        extra_data: Optional[Any] = None
    ) -> Union[str, List[int], Dict]:
        """
        Get business unit hierarchy in various formats.
        Replaces fn_get_bulist PostgreSQL function.
        
        Args:
            bu_id: Business unit ID to start from
            include_parents: Include parent nodes (up the tree)
            include_children: Include child nodes (down the tree)
            return_type: Format to return ('text', 'array', 'jsonb')
            extra_data: Additional data (not used, kept for compatibility)
            
        Returns:
            Business unit IDs in requested format
        """
        # Import here to avoid circular import
        from apps.onboarding.models import Bt
        
        # Get all business units for tree building
        all_bus = list(
            Bt.objects
            .exclude(id__in=[-1])
            .values('id', 'bucode', 'buname', 'parent_id')
        )
        
        if not all_bus:
            return BtManagerORM._format_result([], return_type)
        
        # Build lookup structures
        node_dict = {bu['id']: bu for bu in all_bus}
        children_dict = {}
        parent_dict = {}
        
        for bu in all_bus:
            if bu['parent_id'] and bu['parent_id'] != -1:
                children_dict.setdefault(bu['parent_id'], []).append(bu['id'])
                parent_dict[bu['id']] = bu['parent_id']
        
        result_ids = set()
        
        # Always include the requested node
        if bu_id in node_dict:
            result_ids.add(bu_id)
        
        # Get parents if requested
        if include_parents and bu_id in node_dict:
            current_id = bu_id
            while current_id in parent_dict:
                parent_id = parent_dict[current_id]
                if parent_id != -1 and parent_id != 1:  # Skip special nodes
                    result_ids.add(parent_id)
                    current_id = parent_id
                else:
                    break
        
        # Get children if requested
        if include_children:
            def get_all_children(node_id):
                for child_id in children_dict.get(node_id, []):
                    result_ids.add(child_id)
                    get_all_children(child_id)
            
            get_all_children(bu_id)
        
        # Sort results
        sorted_ids = sorted(list(result_ids))
        
        # Format based on return type
        result = BtManagerORM._format_result(sorted_ids, return_type, node_dict)
        
        return result
    
    @staticmethod
    def _format_result(
        ids: List[int], 
        return_type: str, 
        node_dict: Optional[Dict] = None
    ) -> Union[str, List[int], Dict]:
        """Format results based on requested type"""
        if return_type == 'text':
            return ' '.join(str(id) for id in ids)
        elif return_type == 'array':
            return ids
        elif return_type == 'jsonb':
            if not node_dict:
                return {}
            # Build JSONB format similar to PostgreSQL function
            result = {}
            for bu_id in ids:
                if bu_id in node_dict:
                    bu = node_dict[bu_id]
                    result[str(bu_id)] = {
                        'bucode': bu['bucode'],
                        'buname': bu['buname'],
                        'parent_id': bu['parent_id']
                    }
            return result
        else:
            return ids  # Default to array
    
    @staticmethod
    def get_all_bu_of_client(client_id: int, return_type: str = 'array') -> Union[List[int], str, Dict]:
        """
        Get all business units under a client.
        Replaces the raw SQL call to fn_get_bulist.
        
        Args:
            client_id: Client BU ID
            return_type: Format to return ('array', 'text', 'jsonb')
            
        Returns:
            All BU IDs under the client in requested format
        """
        return BtManagerORM.get_bulist(
            bu_id=client_id,
            include_parents=False,  # Don't include parents
            include_children=True,  # Include all children
            return_type=return_type
        )
    
    @staticmethod
    def get_whole_tree(client_id: int) -> List[int]:
        """
        Get entire BU tree for a client.
        
        Args:
            client_id: Client BU ID
            
        Returns:
            List of all BU IDs in the tree
        """
        return BtManagerORM.get_bulist(
            bu_id=client_id,
            include_parents=True,   # Include parents
            include_children=True,  # Include children
            return_type='array'
        )
    
    @staticmethod
    def get_sitelist_web(client_id: int, people_id: int) -> List[Dict]:
        """
        Get site list for web based on user permissions.
        Replaces fn_get_siteslist_web PostgreSQL function.
        
        Args:
            client_id: Client ID
            people_id: People ID
            
        Returns:
            List of sites the person has access to
        """
        # Import here to avoid circular import
        from apps.peoples.models import People, Pgbelonging
        from apps.onboarding.models import Bt
        
        try:
            person = People.objects.get(id=people_id, client_id=client_id)
        except People.DoesNotExist:
            return []
        
        if person.isadmin:
            # Admin gets all sites under client
            bu_ids = BtManagerORM.get_all_bu_of_client(client_id)
            
            sites = list(
                Bt.objects
                .filter(
                    id__in=bu_ids,
                    enable=True,
                    identifier__tacode='SITE'
                )
                .exclude(bucode__in=['NONE', 'SPS', 'YTPL'])
                .select_related('identifier', 'butype')
                .annotate(
                    butypename=F('butype__taname')
                )
                .values(
                    'id', 'bucode', 'buname', 'butype_id',
                    'butypename', 'enable', 'cdtz', 'mdtz',
                    'cuser_id', 'muser_id'
                )
                .distinct()
            )
            
            return sites
        else:
            # Non-admin: get sites from group assignments and direct assignments
            # Get sites from person's assigned site groups
            site_ids = set()
            
            if person.people_extras and person.people_extras.get('assignsitegroup'):
                group_ids = [int(g) for g in str(person.people_extras['assignsitegroup']).split() if g.strip()]
                
                assigned_sites = (
                    Pgbelonging.objects
                    .filter(pgroup_id__in=group_ids)
                    .values_list('assignsites', flat=True)
                )
                
                for sites in assigned_sites:
                    if sites:
                        if isinstance(sites, list):
                            site_ids.update(sites)
                        else:
                            site_ids.add(sites)
            
            # Get sites from direct assignments (sitepeople table)
            from apps.peoples.models import SitePeople
            from datetime import date
            
            direct_sites = (
                SitePeople.objects
                .filter(
                    people_id=people_id,
                    fromdt__lte=date.today(),
                    uptodt__gte=date.today()
                )
                .values_list('bu_id', flat=True)
            )
            
            site_ids.update(direct_sites)
            
            if not site_ids:
                return []
            
            sites = list(
                Bt.objects
                .filter(
                    id__in=list(site_ids),
                    enable=True
                )
                .exclude(bucode__in=['NONE', 'SPS', 'YTPL'])
                .select_related('identifier', 'butype')
                .annotate(
                    butypename=F('butype__taname')
                )
                .values(
                    'id', 'bucode', 'buname', 'butype_id',
                    'butypename', 'enable', 'cdtz', 'mdtz',
                    'cuser_id', 'muser_id'
                )
                .distinct()
            )
            
            return sites
    
    @staticmethod
    def get_bulist_basedon_idnf(bu_id: int, include_customers: bool = True, include_sites: bool = True) -> str:
        """
        Get business unit list based on identifier filtering.
        Replaces fn_getbulist_basedon_idnf PostgreSQL function.
        
        Args:
            bu_id: Business unit ID to start from
            include_customers: Include CUSTOMER type business units
            include_sites: Include SITE type business units
            
        Returns:
            Space-separated string of business unit IDs
        """
        # Import here to avoid circular import
        from apps.core.queries import TreeTraversal
        
        # Get all business units for tree building
        all_bus = list(
            Bt.objects
            .exclude(id__in=[-1])
            .select_related('identifier')
            .values('id', 'bucode', 'buname', 'parent_id', 'identifier__tacode')
        )
        
        if not all_bus:
            return ''
        
        # Build tree structure starting from the given bu_id
        tree_data = TreeTraversal.build_tree(
            all_bus,
            root_id=bu_id,
            id_field='id',
            code_field='bucode',
            parent_field='parent_id'
        )
        
        # Filter based on identifier types
        filtered_ids = []
        
        # Determine which identifier types to include
        target_tacodes = []
        
        if include_customers and include_sites:
            target_tacodes = ['CUSTOMER', 'SITE']
        elif include_customers and not include_sites:
            target_tacodes = ['CUSTOMER']
        elif not include_customers and include_sites:
            target_tacodes = ['SITE']
        else:
            # Neither customers nor sites - include only CLIENT
            target_tacodes = ['CLIENT']
        
        # Filter tree nodes by identifier type
        for node in tree_data:
            bu_item = next(
                (item for item in all_bus if item['id'] == node['id']),
                None
            )
            
            if bu_item and bu_item['identifier__tacode'] in target_tacodes:
                filtered_ids.append(node['id'])
        
        # Convert to space-separated string
        result = ' '.join(str(id) for id in sorted(filtered_ids))
        
        return result
