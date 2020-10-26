try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

import six

from .key_types import ListIndex
from .reducers import tuple_reducer, path_reducer, dot_reducer, underscore_reducer
from .splitters import tuple_splitter, path_splitter, dot_splitter, underscore_splitter


REDUCER_DICT = {
    "tuple": tuple_reducer,
    "path": path_reducer,
    "dot": dot_reducer,
    "underscore": underscore_reducer,
}

SPLITTER_DICT = {
    "tuple": tuple_splitter,
    "path": path_splitter,
    "dot": dot_splitter,
    "underscore": underscore_splitter,
}


def flatten(
    d,
    reducer="tuple",
    inverse=False,
    max_flatten_depth=None,
    enumerate_types=(),
    keep_empty_types=(),
):
    """Flatten `Mapping` object.

    Parameters
    ----------
    d : dict-like object
        The dict that will be flattened.
    reducer : {'tuple', 'path', 'underscore', 'dot', Callable}
        The key joining method. If a `Callable` is given, the `Callable` will be
        used to reduce.
        'tuple': The resulting key will be tuple of the original keys.
        'path': Use `os.path.join` to join keys.
        'underscore': Use underscores to join keys.
        'dot': Use dots to join keys.
    inverse : bool
        Whether you want invert the resulting key and value.
    max_flatten_depth : Optional[int]
        Maximum depth to merge.
    enumerate_types : Sequence[type]
        Flatten these types using `enumerate`.
        For example, if we set `enumerate_types` to ``(list,)``,
        `list` indices become keys: ``{'a': ['b', 'c']}`` -> ``{('a', 0): 'b', ('a', 1): 'c'}``.
    keep_empty_types : Sequence[type]
        By default, ``flatten({1: 2, 3: {}})`` will give you ``{(1,): 2}``, that is, the key ``3``
        will disappear.
        This is also applied for the types in `enumerate_types`, that is,
        ``flatten({1: 2, 3: []}, enumerate_types=(list,))`` will give you ``{(1,): 2}``.
        If you want to keep those empty values, you can specify the types in `keep_empty_types`:

        >>> flatten({1: 2, 3: {}}, keep_empty_types=(dict,))
        {(1,): 2, (3,): {}}

    Returns
    -------
    flat_dict : dict
    """
    enumerate_types = tuple(enumerate_types)
    flattenable_types = (Mapping,) + enumerate_types
    if not isinstance(d, flattenable_types):
        raise ValueError(
            "argument type %s is not in the flattenalbe types %s"
            % (type(d), flattenable_types)
        )

    # check max_flatten_depth
    if max_flatten_depth is not None and max_flatten_depth < 1:
        raise ValueError("max_flatten_depth should not be less than 1.")

    if isinstance(reducer, str):
        reducer = REDUCER_DICT[reducer]
    flat_dict = {}

    def _flatten(_d, depth, parent=None):
        key_value_iterable = (
            enumerate(_d) if isinstance(_d, enumerate_types) else six.viewitems(_d)
        )
        for key, value in key_value_iterable:
            flat_key = reducer(parent, key)
            if isinstance(value, flattenable_types) and (
                max_flatten_depth is None or depth < max_flatten_depth
            ):
                if value:
                    # recursively build the result
                    _flatten(value, depth=depth + 1, parent=flat_key)
                    continue
                elif not isinstance(value, keep_empty_types):
                    # ignore the key that has an empty value
                    continue

            # add an item to the result
            if inverse:
                flat_key, value = value, flat_key
            if flat_key in flat_dict:
                raise ValueError("duplicated key '{}'".format(flat_key))
            flat_dict[flat_key] = value

    _flatten(d, depth=1)
    return flat_dict


def nested_set_dict(d, keys, value, list_index_types, level=0):
    """Set a value to a sequence of nested keys.

    Parameters
    ----------
    d : Mapping
    keys : Sequence[str]
    value : Any
    list_index_types : Sequence[type]
        Types that will be converted to int and used as list index to build a list.
    """
    assert len(keys) > level
    key = keys[level]
    if isinstance(key, list_index_types):
        key = int(key)

    if len(keys) == level + 1:
        # set the value for the last level
        if key in d:
            raise ValueError("duplicated key '{}'".format(keys))
        d[key] = value
        return

    # set and check the inner object
    inner_key = keys[level + 1]
    if key not in d:
        if isinstance(inner_key, list_index_types):
            inner_d = []
        else:
            inner_d = {}
        d[key] = inner_d
    else:
        inner_d = d[key]
        if isinstance(inner_key, list_index_types):
            if not isinstance(inner_d, list):
                raise ValueError(
                    "Type is not consistant for key '{}'".format(keys[: level + 1])
                )
        elif not isinstance(inner_d, dict):
            raise ValueError(
                "Type is not consistant for key '{}'".format(keys[: level + 1])
            )
    nested_set_dict(inner_d, keys, value, list_index_types, level + 1)


def unflatten(d, splitter="tuple", inverse=False, list_index_types=(ListIndex,)):
    """Unflatten dict-like object.

    Parameters
    ----------
    d : dict-like object
        The dict that will be unflattened.
    splitter : {'tuple', 'path', 'underscore', 'dot', Callable}
        The key splitting method. If a Callable is given, the Callable will be
        used to split `d`.
        'tuple': Use each element in the tuple key as the key of the unflattened dict.
        'path': Use `pathlib.Path.parts` to split keys.
        'underscore': Use underscores to split keys.
        'dot': Use underscores to split keys.
    inverse : bool
        Whether you want to invert the key and value before flattening.
    list_index_types : Sequence[type]
        Types that will be converted to int and used as list index to build a list.

    Returns
    -------
    unflattened_dict : dict
    """
    if isinstance(splitter, str):
        splitter = SPLITTER_DICT[splitter]
    list_index_types = tuple(list_index_types)

    unflattened_dict = {}
    for flat_key, value in six.viewitems(d):
        if inverse:
            flat_key, value = value, flat_key
        key_tuple = splitter(flat_key)
        nested_set_dict(unflattened_dict, key_tuple, value, list_index_types)

    return unflattened_dict
