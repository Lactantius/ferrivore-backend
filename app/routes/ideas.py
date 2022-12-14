""" Routes for ideas """

from flask import Blueprint, jsonify, request, current_app
from flask.wrappers import Response
from flask_jwt_extended import jwt_required, get_jwt
from flask_expects_json import expects_json

from app.models.idea import (
    add_idea,
    random_idea,
    random_unseen_idea,
    popular_unseen_idea,
    get_agreeable_idea,
    get_disagreeable_idea,
    like_idea,
    dislike_idea,
    get_seen_ideas,
    delete_idea,
    get_posted_ideas,
    get_all_seen_ideas_with_user_and_aggregate_reactions,
    get_idea_details,
)

ideas = Blueprint("ideas", __name__, url_prefix="/api/ideas")

post_idea_schema = {
    "type": "object",
    "properties": {
        "url": {"type": "string"},
        "description": {"type": "string"},
        "sourceId": {"type": "string"},
    },
    "required": ["url", "description"],
}

post_reaction_schema = {
    "type": "object",
    "properties": {"type": {"type": "string"}, "agreement": {"type": "number"}},
    "required": ["type"],
}


@ideas.post("/")
@expects_json(post_idea_schema)
@jwt_required()
def post_idea() -> tuple[Response, int]:
    """Post a new idea"""

    claims = get_jwt()
    user_id = claims.get("userId", None)

    data = request.get_json()
    url = data.get("url", None)
    description = data.get("description", None)
    source_id = data.get("sourceId", None)

    idea = add_idea(
        current_app.driver,
        {
            "url": url,
            "description": description,
            "user_id": user_id,
            "source_id": source_id,
        },
    )

    return (jsonify(idea=idea), 201)


@ideas.get("/random")
def get_idea() -> tuple[Response, int]:
    """Get an idea from the database"""

    idea = random_idea(current_app.driver, "fake")

    return (jsonify(idea=idea), 200)


@ideas.get("/random-unseen")
@jwt_required()
def get_unseen_idea() -> tuple[Response, int]:
    """Get a random idea that the user has not yet seen"""

    claims = get_jwt()
    user_id = claims.get("userId", None)

    idea = random_unseen_idea(current_app.driver, user_id)

    if idea is None:
        return (jsonify(msg="We are all out of ideas you haven't seen before."), 404)

    return (jsonify(idea=idea[0]), 200)


@ideas.get("/popular")
@jwt_required()
def get_popular_idea() -> tuple[Response, int]:
    """Get the most liked idea that the user has not yet seen"""
    claims = get_jwt()
    user_id = claims.get("userId", None)

    idea = popular_unseen_idea(current_app.driver, user_id)

    if idea is None:
        return (jsonify(msg="We are all out of idea you haven't seen before."), 404)

    return (jsonify(idea=idea[0]), 200)


@ideas.get("/disagreeable")
@jwt_required()
def disagreeable_idea():
    """Get an idea that the user should be interested in but disagree with"""

    claims = get_jwt()
    user_id = claims.get("userId", None)

    idea = get_disagreeable_idea(current_app.driver, user_id)

    if idea is None:
        return (jsonify(msg="We are all out of ideas for you to disagree with."), 404)

    return (jsonify(idea=idea[0]), 200)


@ideas.get("/agreeable")
@jwt_required()
def agreeable_idea():
    """Get an idea that the user should be interested in but disagree with"""

    claims = get_jwt()
    user_id = claims.get("userId", None)

    idea = get_agreeable_idea(current_app.driver, user_id)

    if idea is None:
        return (jsonify(msg="We are all out of nice ideas."), 404)

    return (jsonify(idea=idea[0]), 200)


@ideas.post("/<string:idea_id>/react")
@expects_json(post_reaction_schema)
@jwt_required()
def react_to_idea(idea_id):

    claims = get_jwt()
    user_id = claims.get("userId", None)

    data = request.get_json()
    type = data["type"]

    if type == "like":
        reaction = like_idea(current_app.driver, user_id, idea_id, data["agreement"])
    else:
        reaction = dislike_idea(current_app.driver, user_id, idea_id)

    if reaction is None:
        return (jsonify(msg="Reaction could not be saved."), 400)

    return (jsonify(reaction=reaction), 200)


@ideas.get("/viewed")
@jwt_required()
def viewed_ideas():
    claims = get_jwt()
    user_id = claims.get("userId", None)

    ideas = get_seen_ideas(current_app.driver, user_id)

    return jsonify(ideas=ideas)


@ideas.get("/viewed-with-relationships")
@jwt_required()
def viewed_ideas_with_relationships():

    claims = get_jwt()
    user_id = claims.get("userId", None)

    ideas = get_all_seen_ideas_with_user_and_aggregate_reactions(
        current_app.driver, user_id
    )

    return jsonify(ideas=ideas)


@ideas.get("/<string:idea_id>/reactions")
@jwt_required()
def idea_reactions(idea_id):

    claims = get_jwt()
    user_id = claims.get("userId", None)

    idea = get_idea_details(current_app.driver, idea_id, True, user_id)
    if idea is None:
        return (jsonify(msg="Reactions not found."), 404)

    return jsonify(
        reactions={
            "userReaction": idea["userReaction"],
            "userAgreement": idea["userAgreement"],
            "allReactions": idea["allReactions"],
            "allAgreement": idea["allAgreement"],
        }
    )


@ideas.get("/<string:idea_id>")
@jwt_required()
def idea_details(idea_id):

    claims = get_jwt()
    user_id = claims.get("userId", None)

    with_reactions = request.args.get("with-reactions", None) == "true"
    with_user_reaction = request.args.get("with-user-reaction", None) == "true"

    if with_user_reaction:
        idea = get_idea_details(current_app.driver, idea_id, True, user_id)
    else:
        idea = get_idea_details(current_app.driver, idea_id, with_reactions)

    if idea is None:
        return (jsonify(msg="Idea not found."), 404)

    return jsonify(idea=idea)


@ideas.delete("/<string:idea_id>")
@jwt_required()
def delete_single_idea(idea_id):

    claims = get_jwt()
    user_id = claims.get("userId", None)

    user_id = claims.get("userId", None)
    query_res = delete_idea(current_app.driver, idea_id, user_id)

    return jsonify({"deleted": query_res})


@ideas.get("/user/<string:user_id>")
@jwt_required()
def posted_by_user(user_id):
    """Get ideas posted by a user"""

    claims = get_jwt()
    current_user = claims.get("userId", None)
    if current_user != user_id:
        return (jsonify(msg="You are not authorized to view this resource"), 403)

    ideas = get_posted_ideas(current_app.driver, user_id)
    return jsonify(ideas=ideas)
