import logging
import colander

from grano.core import db, url_for, celery
from grano.lib.exc import NotImplemented
from grano.model import Relation
from grano.logic import properties as properties_logic
from grano.logic import schemata as schemata_logic
from grano.logic import projects as projects_logic
from grano.logic.references import ProjectRef, AccountRef
from grano.logic.references import SchemaRef, EntityRef
from grano.plugins import notify_plugins


log = logging.getLogger(__name__)


class RelationBaseValidator(colander.MappingSchema):
    author = colander.SchemaNode(AccountRef())
    project = colander.SchemaNode(ProjectRef())


def validate(data):
    """ Due to some fairly weird interdependencies between the different elements
    of the model, validation of relations has to happen in three steps. """

    validator = RelationBaseValidator()
    sane = validator.deserialize(data)
    project = sane.get('project')

    schema_validator = colander.SchemaNode(colander.Mapping())
    schema_validator.add(colander.SchemaNode(SchemaRef(project),
        name='schema'))
    schema_validator.add(colander.SchemaNode(EntityRef(project),
        name='source'))
    schema_validator.add(colander.SchemaNode(EntityRef(project),
        name='target'))

    sane.update(schema_validator.deserialize(data))

    sane['properties'] = properties_logic.validate(
        data.get('properties', []),
        [sane.get('schema')],
        name='properties')
    return sane


@celery.task
def _relation_changed(relation_id):
    """ Notify plugins about changes to a relation. """
    log.debug("Processing change in relation: %s", relation_id)
    def _handle(obj):
        obj.relation_changed(relation_id)
    notify_plugins('grano.relation.change', _handle)


def save(data, relation=None):
    """ Save or update a relation with the given properties. """

    data = validate(data)

    if relation is None:
        relation = Relation()
        relation.project = data.get('project')
        relation.author = data.get('author')
        db.session.add(relation)

    relation.source = data.get('source')
    relation.target = data.get('target')
    relation.schema = data.get('schema')


    prop_names = set()
    for name, prop in data.get('properties').items():
        prop_names.add(name)
        prop['name'] = name
        prop['author'] = data.get('author')
        properties_logic.save(relation, prop)

    for prop in relation.properties:
        if prop.name not in prop_names:
            prop.active = False

    db.session.flush()    
    _relation_changed.delay(relation.id)
    return relation


def delete(relation):
    raise NotImplemented()


def to_rest_base(relation):
    from grano.logic import entities as entities_logic
    return {
        'id': relation.id,
        'properties': {},
        'project': projects_logic.to_rest_index(relation.project),
        'api_url': url_for('relations_api.view', id=relation.id),
        'schema': schemata_logic.to_rest_index(relation.schema),
        'source': entities_logic.to_rest_index(relation.source),
        'target': entities_logic.to_rest_index(relation.target)
    }


def to_rest(relation):
    data = to_rest_base(relation)
    for prop in relation.active_properties:
        name, prop = properties_logic.to_rest(prop)
        data['properties'][name] = prop
    return data


def to_rest_index(relation):
    data = to_rest_base(relation)
    for prop in relation.active_properties:
        name, prop = properties_logic.to_rest_index(prop)
        data['properties'][name] = prop
    return data
