//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

library truebex.api;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:collection/collection.dart';
import 'package:http/http.dart';
import 'package:intl/intl.dart';
import 'package:meta/meta.dart';

part 'api_client.dart';
part 'api_helper.dart';
part 'api_exception.dart';
part 'auth/authentication.dart';
part 'auth/api_key_auth.dart';
part 'auth/oauth.dart';
part 'auth/http_basic_auth.dart';
part 'auth/http_bearer_auth.dart';

part 'api/auth_api.dart';
part 'api/market_api.dart';
part 'api/members_api.dart';
part 'api/ops_api.dart';
part 'api/panoramas_api.dart';
part 'api/presence_api.dart';
part 'api/projects_api.dart';
part 'api/snapshots_api.dart';

part 'model/availability.dart';
part 'model/error_envelope.dart';
part 'model/google_login.dart';
part 'model/member.dart';
part 'model/member_list.dart';
part 'model/op_in.dart';
part 'model/open_project.dart';
part 'model/operation.dart';
part 'model/operation_action.dart';
part 'model/panorama_set.dart';
part 'model/panorama_sets.dart';
part 'model/presence.dart';
part 'model/presence_answer.dart';
part 'model/presence_in.dart';
part 'model/presence_list.dart';
part 'model/presence_view.dart';
part 'model/price.dart';
part 'model/price_item.dart';
part 'model/priced_item.dart';
part 'model/prices_answer.dart';
part 'model/prices_request.dart';
part 'model/product_answer.dart';
part 'model/product_variant.dart';
part 'model/project_list.dart';
part 'model/project_owner.dart';
part 'model/project_quota.dart';
part 'model/project_record.dart';
part 'model/pull_page.dart';
part 'model/push_answer.dart';
part 'model/push_in.dart';
part 'model/push_result.dart';
part 'model/search_answer.dart';
part 'model/search_hit.dart';
part 'model/set_state.dart';
part 'model/snapshot.dart';
part 'model/snapshot_file.dart';
part 'model/snapshot_files.dart';
part 'model/snapshot_summary.dart';
part 'model/tile_face.dart';
part 'model/tile_faces.dart';
part 'model/tile_manifest.dart';
part 'model/tile_view.dart';
part 'model/token.dart';
part 'model/user_login.dart';
part 'model/user_out.dart';
part 'model/view_in.dart';


/// An [ApiClient] instance that uses the default values obtained from
/// the OpenAPI specification file.
var defaultApiClient = ApiClient();

const _delimiters = {'csv': ',', 'ssv': ' ', 'tsv': '\t', 'pipes': '|'};
const _dateEpochMarker = 'epoch';
const _deepEquality = DeepCollectionEquality();
final _dateFormatter = DateFormat('yyyy-MM-dd');
final _regList = RegExp(r'^List<(.*)>$');
final _regSet = RegExp(r'^Set<(.*)>$');
final _regMap = RegExp(r'^Map<String,(.*)>$');

bool _isEpochMarker(String? pattern) => pattern == _dateEpochMarker || pattern == '/$_dateEpochMarker/';
