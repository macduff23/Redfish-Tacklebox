#! /usr/bin/python
# Copyright Notice:
# Copyright 2020 DMTF. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/Redfish-Tacklebox/blob/master/LICENSE.md

"""
Logs Module

File : logs.py

Brief : This file contains the definitions and functionalities for interacting
        with the log service for a given Redfish service
"""

import shutil

from .messages import verify_response
from enum import Enum

class RedfishLogServiceNotFoundError( Exception ):
    """
    Raised when a matching log service cannot be found
    """
    pass

class RedfishClearLogNotFoundError( Exception ):
    """
    Raised when a log service does not contain the clear log action
    """
    pass

class log_container( Enum ) :
    """
    Types of resources that contain log services
    """
    MANAGER = "Managers"
    CHASSIS = "Chassis"
    SYSTEM = "Systems"

def get_log_entries( context, container_type = log_container.MANAGER, container_id = None, log_service_id = None ):
    """
    Finds the log entries of a log service matching the given ID

    Args:
        context: The Redfish client object with an open session
        container_type: The type of resource containing the log service (manager, system, or chassis)
        container_id: The container instance with the log service; if None, perform on the only container
        log_service_id: The log service with the logs; if None, perform on the only log service

    Returns:
        An array of log entries
    """

    log_service = get_log_service( context, container_type, container_id, log_service_id )

    # Read in the log entries
    log_entries = []
    log_entry_col = context.get( log_service.dict["Entries"]["@odata.id"] )
    log_entries.extend( log_entry_col.dict["Members"] )

    # If a next link is provided, iterate over it and add to the log entry list
    while "Members@odata.nextLink" in log_entry_col.dict:
        log_entry_col = context.get( log_entry_col.dict["Members@odata.nextLink"] )
        log_entries.extend( log_entry_col.dict["Members"] )

    return log_entries

def print_log_entries( log_entries, details = False ):
    """
    Prints a set of log entries in a table

    Args:
        log_entries: The log entries to print
        details: Flag indicating if details should be displayed
    """

    # Set up templates
    console_size = shutil.get_terminal_size(fallback=(80, 24))
    message_size = console_size.columns - 38
    entry_line_format = "  {:5s} | {:25s} | {}"
    detail_line_format = "  {:33s} | {}: {}"
    detail_list = [ "Severity", "EntryType", "OemRecordFormat", "EntryCode", "OemLogEntryCode", "SensorType", "OemSensorType",
        "GeneratorId", "SensorNumber", "EventType", "EventId", "EventGroupId", "MessageId", "MessageArgs" ]
    print( entry_line_format.format( "Id", "Timestamp", "Message" ) )

    # Go through each entry and print the info
    for entry in log_entries:
        timestamp_property = "Created"
        if "EventTimestamp" in entry:
            timestamp_property = "EventTimestamp"
        print( entry_line_format.format( entry["Id"], entry.get( timestamp_property, "Unknown" ), entry["Message"].replace( "\n", "; " )[:message_size] ) )
        if details:
            for detail in detail_list:
                if detail in entry:
                    print( detail_line_format.format( "", detail, entry[detail] ) )

def clear_log_entries( context, container_type = log_container.MANAGER, container_id = None, log_service_id = None ):
    """
    Clears the log entries of a log service matching the given ID

    Args:
        context: The Redfish client object with an open session
        container_type: The type of resource containing the log service (manager, system, or chassis)
        container_id: The container instance with the log service; if None, perform on the only container
        log_service_id: The log service with the logs; if None, perform on the only log service

    Returns:
        The response of the action
    """

    log_service = get_log_service( context, container_type, container_id, log_service_id )

    # Find the ClearLog action
    if "Actions" not in log_service.dict:
        raise RedfishClearLogNotFoundError( "Log service does not support ClearLog" )
    if "#LogService.ClearLog" not in log_service.dict["Actions"]:
        raise RedfishClearLogNotFoundError( "Log service does not support ClearLog" )
    clear_uri = log_service.dict["Actions"]["#LogService.ClearLog"]["target"]

    # Clear the log
    response = context.post( clear_uri, body = {} )
    verify_response( response )
    return response

def get_log_service( context, container_type = log_container.MANAGER, container_id = None, log_service_id = None ):
    """
    Finds a log service matching the given ID and returns its resource

    Args:
        context: The Redfish client object with an open session
        container_type: The type of resource containing the log service (manager, system, or chassis)
        container_id: The container instance to locate; if None, perform on the only container
        log_service_id: The log service to locate; if None, perform on the only log service

    Returns:
        The log service resource
    """

    # Get the Service Root to find the resource collection
    service_root = context.get( "/redfish/v1/" )
    if container_type.value not in service_root.dict:
        # No resource collection
        raise RedfishLogServiceNotFoundError( "Service does not contain a {} collection".format( container_type.value ) )

    # Get the resource collection and iterate through its collection to find the matching container instance
    resource_col = context.get( service_root.dict[container_type.value]["@odata.id"] )
    if container_id is None:
        if len( resource_col.dict["Members"] ) == 1:
            resource = context.get( resource_col.dict["Members"][0]["@odata.id"] )
            container_id = resource.dict["Id"]
        else:
            raise RedfishLogServiceNotFoundError( "Service does not contain exactly one resource in {}; a target container needs to be specified".format( container_type.value ) )
    else:
        container_found = False
        for resource_member in resource_col.dict["Members"]:
            resource = context.get( resource_member["@odata.id"] )
            if resource.dict["Id"] == container_id:
                container_found = True
                break
        if not container_found:
            raise RedfishLogServiceNotFoundError( "Service does not contain a resource in {} called {}".format( container_type.value, container_id ) )

    # Go through the container to find the log service collection
    if "LogServices" not in resource.dict:
        # No log services
        raise RedfishLogServiceNotFoundError( "{} does not contain a log service collection".format( container_id ) )

    # Get the log service collection and iterate through its collection
    log_serv_col = context.get( resource.dict["LogServices"]["@odata.id"] )
    if log_service_id is None:
        if len( log_serv_col.dict["Members"] ) == 1:
            return context.get( log_serv_col.dict["Members"][0]["@odata.id"] )
        else:
            raise RedfishLogServiceNotFoundError( "{} does not contain exactly one log service; a target log service needs to be specified".format( container_id ) )
    else:
        for log_serv_member in log_serv_col.dict["Members"]:
            log_serv = context.get( log_serv_member["@odata.id"] )
            if log_serv.dict["Id"] == log_service_id:
                return log_serv

    raise RedfishLogServiceNotFoundError( "{} does not contain a log service called {}".format( container_id, log_service_id ) )
