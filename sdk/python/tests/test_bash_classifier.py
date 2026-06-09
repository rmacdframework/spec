"""Tests for the Bash command → RMACD classifier."""

from __future__ import annotations

import pytest

from rmacd.models import Operation as Op
from rmacd.registry import classify_bash_command, make_bash_classifier


def op(cmd: str, **kw) -> Op:
    return classify_bash_command(cmd, **kw).operation


class TestRegressionBundledFlags:
    """Bundled short flags must still trigger per-flag rules (else under-class)."""

    def test_sed_bundled_inplace_is_change(self):
        # `sed -ni` bundles -n and -i; the -i must still elevate to Change.
        assert op("sed -ni s/a/b/ f") == Op.CHANGE
        assert op("sed -ne s/a/b/ f") == Op.READ          # -n -e, no in-place
        assert op("sed -i.bak s/a/b/ f") == Op.CHANGE      # -i with backup suffix

    def test_vim_bundled_readonly_is_read(self):
        assert op("vim -Rn f") == Op.READ                  # -R read-only bundled

    def test_find_long_flags_unaffected(self):
        assert op("find . -name x -delete") == Op.DELETE   # single-dash long flag
        assert op("find . -exec rm {} +") == Op.CHANGE


class TestRegressionRedirects:
    """Redirects detected from tokens — quoted `>` / `->` are not false positives."""

    def test_quoted_gt_is_not_a_redirect(self):
        assert op('echo "a > b"') == Op.READ
        assert op('echo "migrate A -> B"') == Op.READ

    def test_real_redirects_still_detected(self):
        assert op("echo hi > /etc/hosts") == Op.CHANGE
        assert op("echo hi >f") == Op.CHANGE               # glued >file
        assert op("grep x f 2>err") == Op.CHANGE


class TestRegressionSubshellsAndWrappers:
    def test_nested_direct_dangerous_binary_is_caught(self):
        # iterative extraction unwraps nested $(...) so a nested rm is seen
        assert op("echo $(echo $(rm -rf x))") == Op.DELETE

    def test_bash_c_recurses_into_command_string(self):
        assert op('bash -c "rm -rf /"') == Op.DELETE
        assert op('sh -c "ls -la"') == Op.READ
        assert op("bash deploy.sh") == Op.CHANGE           # opaque script → fail-closed


class TestRegressionTar:
    def test_tar_create_is_add(self):
        assert op("tar -czf a.tgz dir") == Op.ADD

    def test_tar_remove_files_is_delete(self):
        assert op("tar --remove-files -czf a.tgz dir") == Op.DELETE
        assert op("tar --delete -f a.tar member") == Op.DELETE


class TestRegressionGlobalFlags:
    """A global option before the verb must not be mistaken for the subcommand."""

    def test_kubectl_namespace_flag(self):
        assert op("kubectl -n prod delete pod web") == Op.DELETE
        assert op("kubectl -n ns get pods") == Op.READ

    def test_git_dash_C(self):
        assert op("git -C /repo commit -m x") == Op.CHANGE
        assert op("git -c core.editor=vi push") == Op.CHANGE

    def test_docker_context_flag(self):
        assert op("docker --context prod rm container") == Op.DELETE

    def test_quoted_arg_matching_a_verb_does_not_false_match(self):
        # "delete" inside a commit message is one token, not the verb.
        assert op('git commit -m "fix the delete bug"') == Op.CHANGE


class TestRegressionWrappers:
    """timeout/nice consume a value arg; eval runs its argument."""

    def test_timeout_value_then_command(self):
        assert op("timeout 5 rm -rf /") == Op.DELETE
        assert op("timeout 5s curl -X DELETE http://x") == Op.DELETE
        assert op("timeout 30 git commit -m x") == Op.CHANGE

    def test_nice_priority(self):
        assert op("nice -n 10 rm x") == Op.DELETE
        assert op("nice -10 rm x") == Op.DELETE
        assert op("nice cat f") == Op.READ

    def test_eval_classifies_argument(self):
        assert op('eval "rm -rf x"') == Op.DELETE
        assert op("eval ls") == Op.READ

    def test_stacked_wrappers(self):
        assert op("sudo timeout 5 rm x") == Op.DELETE

    def test_sudo_valued_flags_consume_value(self):
        assert op("sudo -u root rm -rf /var") == Op.DELETE   # -u eats 'root'
        assert op("sudo -H rm -rf x") == Op.DELETE           # -H is boolean, keep rm
        assert op("sudo cat f") == Op.READ
        assert op("sudo -u app git -C /r commit -m x") == Op.CHANGE  # stacked

    def test_flag_with_equals_value_matches(self):
        # `--in-place=.bak` must match the `--in-place` elevation rule.
        assert op("sed --in-place=.bak s/a/b/ f") == Op.CHANGE


class TestBaseCommands:
    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("cat /etc/hosts", Op.READ),
            ("ls -la", Op.READ),
            ("grep foo bar.txt", Op.READ),
            ("head -n5 f", Op.READ),
            ("wc -l f", Op.READ),
            ("mv a b", Op.MOVE),
            ("rename s/a/b/ *.txt", Op.MOVE),
            ("cp a b", Op.ADD),
            ("mkdir -p out", Op.ADD),
            ("touch newfile", Op.ADD),
            ("ln -s a b", Op.ADD),
            ("chmod 600 secret", Op.CHANGE),
            ("chown root:root f", Op.CHANGE),
            ("pico /etc/hosts", Op.CHANGE),
            ("nano f", Op.CHANGE),
            ("vim f", Op.CHANGE),
            ("rm -rf build", Op.DELETE),
            ("rmdir d", Op.DELETE),
            ("shred -u secret", Op.DELETE),
        ],
    )
    def test_base(self, cmd, expected):
        assert op(cmd) == expected


class TestSwitchSensitivity:
    def test_sed_print_vs_inplace(self):
        assert op('sed -n "s/a/b/p" f') == Op.READ
        assert op('sed -i "s/a/b/" f') == Op.CHANGE
        assert op('sed --in-place "s/a/b/" f') == Op.CHANGE

    def test_find_read_vs_delete_vs_exec(self):
        assert op('find . -name "*.log"') == Op.READ
        assert op('find . -name "*.tmp" -delete') == Op.DELETE
        assert op('find . -exec rm {} +') == Op.CHANGE

    def test_curl_get_vs_write_vs_upload(self):
        assert op("curl https://x/y") == Op.READ
        assert op("curl -o out.json https://x/y") == Op.ADD
        assert op("curl -T file https://x/y") == Op.CHANGE

    def test_rsync_move_vs_delete(self):
        assert op("rsync -a src/ dst/") == Op.MOVE
        assert op("rsync -a --delete src/ dst/") == Op.DELETE

    def test_awk_is_read_by_default(self):
        assert op('awk "{print $1}" f') == Op.READ


class TestEditorViewMode:
    """pico/nano/vim edit (Change) by default; view mode flips them to Read.

    The per-binary scoping matters: -v is *view* for pico but *verbose* for
    cp/rm, so it must not globally downgrade those.
    """

    def test_pico_edits_by_default(self):
        assert op("pico /etc/nginx.conf") == Op.CHANGE

    def test_pico_view_flag_flips_to_read(self):
        assert op("pico -v /etc/passwd") == Op.READ
        assert op("pico --view /etc/passwd") == Op.READ
        assert op("nano -v f") == Op.READ

    def test_pico_cosmetic_flags_stay_change(self):
        assert op("pico -w -E -l -T 4 file") == Op.CHANGE
        assert op("pico -B -C /backups file") == Op.CHANGE
        assert op("pico -R locked.conf") == Op.CHANGE  # restricted mode still saves

    def test_vim_readonly_flags(self):
        assert op("vim -R /etc/hosts") == Op.READ
        assert op("vim -M f") == Op.READ
        assert op("vim file") == Op.CHANGE

    def test_help_version_print_and_exit(self):
        assert op("pico --version") == Op.READ
        assert op("git --help") == Op.READ
        assert op("rm --help") == Op.READ  # help never deletes

    def test_short_v_is_verbose_elsewhere(self):
        # -v must NOT be treated as view for non-editor binaries.
        assert op("cp -v a b") == Op.ADD
        assert op("rm -v x") == Op.DELETE


class TestNetworkTools:
    def test_nslookup_all_switches_are_read(self):
        for c in [
            "nslookup example.com",
            "nslookup -type=mx example.com",
            "nslookup -query=ns -recurse example.com 8.8.8.8",
            "nslookup -debug -port=5353 example.com",
        ]:
            assert op(c) == Op.READ
        # the mutating DNS counterpart is a different binary
        assert op("nsupdate -k key") == Op.CHANGE
        assert op("dig +short example.com") == Op.READ


class TestSubcommandDriven:
    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("git log", Op.READ),
            ("git status", Op.READ),
            ("git add .", Op.ADD),
            ("git mv a b", Op.MOVE),
            ("git commit -m x", Op.CHANGE),
            ("git push", Op.CHANGE),
            ("git rm f", Op.DELETE),
            ("kubectl get pods", Op.READ),
            ("kubectl apply -f x.yaml", Op.CHANGE),
            ("kubectl delete pod p", Op.DELETE),
            ("docker ps", Op.READ),
            ("docker run img", Op.ADD),
            ("docker rm c", Op.DELETE),
            ("systemctl status nginx", Op.READ),
            ("systemctl restart nginx", Op.CHANGE),
            ("aws s3 ls", Op.READ),
            ("aws s3 rm s3://b/k", Op.DELETE),
            ("apt install nginx", Op.ADD),
            ("apt remove nginx", Op.DELETE),
            ("pip install requests", Op.ADD),
            ("pip uninstall requests", Op.DELETE),
        ],
    )
    def test_subcommands(self, cmd, expected):
        assert op(cmd) == expected


class TestCloudAndInfra:
    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("gcloud compute instances list", Op.READ),
            ("gcloud compute instances create vm", Op.ADD),
            ("gcloud sql instances patch x", Op.CHANGE),
            ("gcloud compute instances delete vm", Op.DELETE),
            ("az vm list", Op.READ),
            ("az webapp create -n a", Op.ADD),
            ("az group delete -n rg", Op.DELETE),
            ("terraform plan", Op.READ),
            ("terraform validate", Op.READ),
            ("terraform fmt", Op.CHANGE),
            ("terraform apply -auto-approve", Op.CHANGE),
            ("terraform destroy", Op.DELETE),
            ("helm list", Op.READ),
            ("helm install r chart", Op.ADD),
            ("helm upgrade r chart", Op.CHANGE),
            ("helm uninstall r", Op.DELETE),
        ],
    )
    def test_cloud_and_iac(self, cmd, expected):
        assert op(cmd) == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("aws ec2 terminate-instances --instance-ids i", Op.DELETE),
            ("aws s3api delete-object --bucket b --key k", Op.DELETE),
            ("aws cloudformation create-stack --stack-name s", Op.ADD),
            ("aws ec2 describe-instances", Op.READ),
            ("aws logs put-log-events", Op.CHANGE),
        ],
    )
    def test_aws_hyphenated_verbs(self, cmd, expected):
        assert op(cmd) == expected

    def test_ansible_check_is_dry_run(self):
        assert op("ansible-playbook site.yml") == Op.CHANGE
        assert op("ansible-playbook site.yml --check") == Op.READ

    def test_make_dry_run(self):
        assert op("make") == Op.CHANGE
        assert op("make -n") == Op.READ
        assert op("make --dry-run") == Op.READ


class TestPackageAndDb:
    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("yum install nginx", Op.ADD),
            ("dnf remove nginx", Op.DELETE),
            ("brew upgrade", Op.CHANGE),
            ("brew list", Op.READ),
            ("psql -c 'SELECT 1'", Op.CHANGE),   # SQL opaque → conservative
            ("mysql -e 'DROP TABLE t'", Op.CHANGE),
            ("mysqldump db", Op.READ),           # export = read
            ("pg_dump db", Op.READ),
        ],
    )
    def test_pkg_and_db(self, cmd, expected):
        assert op(cmd) == expected


class TestCurlMethods:
    def test_curl_methods(self):
        assert op("curl https://api/x") == Op.READ
        assert op("curl -O https://f") == Op.ADD
        assert op("curl -T file https://api/x") == Op.CHANGE
        assert op("curl -X POST -d @body https://api/x") == Op.CHANGE
        assert op("curl -X DELETE https://api/x") == Op.DELETE

    def test_awk_writes_elevate(self):
        assert op('awk "{print $1}" f') == Op.READ
        assert op('awk "{print > \\"out\\"}" f') == Op.CHANGE

    def test_global_dry_run_is_read(self):
        assert op("rsync -a --dry-run s d") == Op.READ
        assert op("git push --dry-run") == Op.READ
        assert op("apt install x --dry-run") == Op.READ


class TestComposition:
    def test_pipeline_all_read(self):
        assert op("cat f | grep x | sort | uniq -c") == Op.READ

    def test_pipeline_takes_max(self):
        assert op("ls && rm -rf /tmp/x") == Op.DELETE
        assert op("cat f ; chmod 600 g") == Op.CHANGE

    def test_redirect_is_a_write(self):
        assert op("echo hi > /etc/hosts") == Op.CHANGE
        assert op("cat a >> b") == Op.CHANGE
        # a redirect on an otherwise-read command still elevates
        assert op("grep x f > out") == Op.CHANGE

    def test_sudo_and_wrappers_stripped(self):
        assert op("sudo systemctl restart nginx") == Op.CHANGE
        assert op("sudo rm -rf /var/log/x") == Op.DELETE
        assert op("env FOO=1 cat f") == Op.READ
        assert op("time ls") == Op.READ

    def test_command_substitution_is_classified(self):
        assert op("echo $(rm -rf x)") == Op.DELETE
        assert op("echo `git commit -m x`") == Op.CHANGE


class TestFailClosed:
    def test_unknown_binary_defaults_to_change(self):
        assert op("frobnicate --hard") == Op.CHANGE

    def test_unknown_default_is_configurable(self):
        assert op("frobnicate", default=Op.DELETE) == Op.DELETE

    def test_empty_command_is_read(self):
        assert op("") == Op.READ
        assert op("   ") == Op.READ


class TestRegistryAdapter:
    def test_make_bash_classifier_shape(self):
        classify = make_bash_classifier()
        operation, tier, target = classify({"command": "rm -rf build"})
        assert operation == Op.DELETE
        assert tier is None
        assert target == "bash:rm"

    def test_enforce_tool_call_with_bash_2d(self):
        # Bash classification is operation-level (tier is None), so it pairs
        # with a 2D profile (operations × autonomy). For 3D, supply a tier via
        # a separate path→resource resolver.
        from rmacd import PolicyEnforcer, RMACDPermissionDeniedError
        from rmacd.approval import AutoApproveGateway
        from rmacd.models import Profile2D
        from rmacd.registry import ToolDefinition, ToolsRegistry

        profile = Profile2D(
            profile_id="rmacd-2d-ops", profile_name="Ops", model="two-dimensional",
            version="1.0", permissions=[Op.READ, Op.MOVE, Op.ADD, Op.CHANGE],  # no Delete
        )
        reg = ToolsRegistry()
        reg.register_tool(ToolDefinition("Bash", "Shell", Op.CHANGE,
                                         classifier=make_bash_classifier()))
        enf = PolicyEnforcer(profile=profile, agent_id="a", registry=reg,
                             approval_gateway=AutoApproveGateway())

        assert enf.enforce_tool_call("Bash", {"command": "ls -la"}).operation == Op.READ
        assert enf.enforce_tool_call("Bash", {"command": "sed -i s/a/b/ f"}).operation == Op.CHANGE
        with pytest.raises(RMACDPermissionDeniedError):  # profile lacks Delete
            enf.enforce_tool_call("Bash", {"command": "rm -rf build"})
