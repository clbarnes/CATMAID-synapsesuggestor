# -*- coding: utf-8 -*-
import logging
from string import Formatter
import json

from six import string_types
import numpy as np

from django.db import connection

from synapsesuggestor.models import ProjectSynapseSuggestionWorkflow


logger = logging.getLogger(__name__)


def flatten(arg):
    elements = []
    if isinstance(arg, string_types):
        elements.append(arg)
    elif isinstance(arg, dict):
        elements.append(json.dumps(arg))
    else:
        try:
            for item in arg:
                elements.extend(flatten(item))
        except TypeError:
            elements.append(arg)
    return elements


def list_into_query(query, arg_lst, fmt='%s'):
    """
    Convert simple query with list of arguments into mogrifier-friendly form

    Args:
      query(str): A string with a single {} in it
      arg_lst(list): List of arguments to supply to SQL
      fmt(str, optional): Placeholder to use for each element (e.g. use this to wrap stuff in brackets), or to account for tuples (Default value = '%s')

    Returns:
      (str, tuple): The two arguments to pass to cursor.execute

    Examples:
    >>> list_into_query("DELETE FROM table_name WHERE id IN ({})", [1, 2, 3])
    >>> ("DELETE FROM table_name WHERE id IN (%s, %s, %s)", (1, 2, 3))

    >>> list_into_query("INSERT INTO table_name (a, b) VALUES ({})", [[1, 2], [3, 4]], fmt='(%s, %s)')
    >>> ("INSERT INTO table_name (a, b) VALUES ((%s, %s), (%s, %s))", (1, 2, 3, 4))
    """
    # assert set(fmt).issubset(',()%s ')

    arg_str = ', '.join(fmt for _ in arg_lst)
    final_query = query.format(arg_str)
    final_args = tuple(flatten(arg_lst))

    logger.debug('Preparing SQL query for form \n%s with arguments %s', final_query, str(final_args))
    return final_query, final_args


def list_into_query_multi(query, fmt=None, **kwargs):
    """
    Convert complex query with several lists of arguments into mogrifier-friendly form

    Args:
      query(str): Format string using keyword format, e.g. 'Hi, my name is {name} and I am {age} years old'
      fmt(dict, optional): Mapping from keywords to SQL-friendly format strings (defaults to '%s' for everything)
      **kwargs: Mapping from keywords to argument lists

    Returns:
      (str, tuple): The two arguments to pass to cursor.execute

    Examples
    --------
    >>> query = "INSERT INTO table_name1 (a, b) VALUES ({first}); INSERT INTO table_name2 (a, b) VALUES ({second});"
    >>> list_into_query_multi(query, fmt={'second': '(%s, %s)'}, first=[1, 2, 3], second=[[1,2], [3,4]])
    >>> ('INSERT INTO table_name1 (a, b) VALUES (%s, %s, %s); INSERT INTO table_name2 (a, b) VALUES ((%s, %s), (%s, %s));',
    >>>     [1, 2, 3, 1, 2, 3, 4])
    """
    if fmt is None:
        fmt = dict()
    # assert all(set(value).issubset(',()%s ') for value in fmt.values())

    formatter = Formatter()
    arg_order = [arg_name for _, arg_name, _, _ in formatter.parse(query) if arg_name]
    arg_strs = {
        arg_name: ', '.join(fmt.get(arg_name, '%s') for _ in arg_list)
        for arg_name, arg_list in kwargs.items()
    }
    final_args = flatten(kwargs[arg_name] for arg_name in arg_order)
    final_query = query.format(**arg_strs)

    logger.debug('Preparing SQL query for form \n%s \nwith arguments \n%s', final_query, str(final_args))
    return final_query, tuple(final_args)


def get_translation_resolution(project_id, ssw_id, cursor=None):
    """
    Return the translation and resolution for converting between stack and project coordinates.

    Args:
      project_id(int):
      ssw_id(int): Synapse suggestion workflow ID
      cursor(django.db.connection.cursor, optional):  (Default value = None)

    Returns:
      tuple:  (numpy.ndarray, numpy.ndarray)
        Translation is the location of the stack origin, in project space
        Resolution is the size of a stack pixel, in project space
    """
    if cursor is None:
        cursor = connection.cursor()

    cursor.execute('''
        SELECT 
          (ps.translation).x, (ps.translation).y, (ps.translation).z, 
          (stack.resolution).x, (stack.resolution).y, (stack.resolution).z  
        FROM synapse_suggestion_workflow ssw
          INNER JOIN synapse_detection_tiling tiling
            ON ssw.synapse_detection_tiling_id = tiling.id
          INNER JOIN stack
            ON tiling.stack_id = stack.id
          INNER JOIN project_stack ps
            ON ps.stack_id = stack.id
          WHERE ps.project_id = %s
            AND ssw.id = %s
          LIMIT 1;
    ''', (project_id, ssw_id))

    trans_res = cursor.fetchone()

    return np.array(trans_res[:3]), np.array(trans_res[-3:])


# def get_or_create_algo_version(request, project_id=None):
#     """
#
#     Parameters
#     ----------
#     request
#     project_id
#
#     Returns
#     -------
#
#     """
#     hashcode = request.POST['hashcode']
#     notes = request.POST.get('notes', '')
#
#     cursor = connection.cursor()
#
#     cursor.execute('''
#         INSERT INTO synapse_suggestion_algorithm AS ssa (hashcode, notes)
#           VALUES (%s, %s) AS new (hashcode, notes)
#           ON CONFLICT (ssa.hashcode) DO NOTHING
#           RETURNING (ssa.id, ssa.hashcode, ssa.date, ssa.notes);
#     ''', (hashcode, notes))
#     data = dict()
#     data['id'], data['hashcode'], data['date'], data['notes'] = cursor.fetchone()
#     return JsonResponse(data)


def get_project_SS_workflow(project_id, ssw_id=None):
    """
    Given a project ID, return a ProjectSynapseSuggestionWorkflow object.

    If ssw_id is given, return the PSSW associated with the project and that SSW. If ssw_id is not given,
    return the most recent PSSW associated with the project.
    """
    if ssw_id is None:
        return get_most_recent_project_SS_workflow(project_id)
    else:
        return ProjectSynapseSuggestionWorkflow.objects.get(synapse_suggestion_workflow_id=ssw_id,
                                                            project_id=project_id)


def get_most_recent_project_SS_workflow(project_id):
    """Given a project ID, return the ProjectSynapseSuggestionWorkflow row most recently created in that project"""
    return ProjectSynapseSuggestionWorkflow.objects.filter(project_id=project_id).order_by('-created').first()
