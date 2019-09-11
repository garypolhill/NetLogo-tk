#!/usr/bin/perl
#
# dotworld.pl
#
# Gary Polhill, 9 April 2012
#
# Script taking an export-world as input and producing a DOT file for graphing
# households.
#
# By default, the DOT file is configured to show as much information as
# possible about each link and node, including non-null settings of any
# variable. Use -nodata to suppress this.
#
# The label displayed for each node in the graph is, by default, any label
# used to refer to the turtle in the link data (e.g. {breed 123}). To use a
# different label, use the -label option for each breed you want to give a
# different label to. The first argument to the -label option is the name
# of the breed; the second argument is the variable to use to obtain the
# label.
#
# The remaining arguments to the script provide the name of a DOT file, the
# name of a netlogo export-world output CSV file, and arguments describing the
# graph you want to draw. The first of these argument specifies nodes to
# 'start' drawing the graph with. This is given as a <var>=<value> pair -- e.g.
# breed=households to get all households, or household-id=hh23 to get a
# particular household. The remaining arguments stipulate link breeds to
# 'expand' the graph with. At least one must be provided, and the link breed
# may be repeated.

use FindBin;
use lib $FindBin::Bin;

use strict;
use nlogo2R;

my %nodelabels;
my $data = 1;

while($ARGV[0] =~ /^-/) {
  my $opt = shift(@ARGV);

  if($opt eq '-label') {
    my $breed = shift(@ARGV);
    my $label = shift(@ARGV);

    $nodelabels{'{breed '.$breed.'}'} = $label;
  }
  elsif($opt eq '-nodata') {
    $data = 0;
  }
  else {
    die "Option not recognised: $opt\n";
  }
}

if(scalar(@ARGV) < 4) {
  die "Usage: $0 [-nodata] {-label <breed> <var>} <DOT file> <world file> ",
  "<start node var>=<start node value> <link breeds...>\n";
}

my $dotfile = shift(@ARGV);

my $worldfile = shift(@ARGV);

my $startnodes = shift(@ARGV);

my ($startkey, $startvalue) = split(/=/, $startnodes);

my @addedges = @ARGV;

my $turtles = nlogo2R::readturtles($worldfile);

my $links = nlogo2R::readlinks($worldfile);

my @nodes;

if($startkey eq 'who') {
  push(@nodes, $turtles->{$startkey});
}
elsif($startkey eq 'breed') {
  foreach my $turtle (values(%$turtles)) {
    if($turtle->{$startkey} eq '{breed '.$startvalue.'}') {
      push(@nodes, $turtle);
    }
  }
}
else {
  foreach my $turtle (values(%$turtles)) {
    if($turtle->{$startkey} eq $startvalue) {
      push(@nodes, $turtle);
    }
  }
}

if(scalar(@nodes) == 0) {
  die "Got no start nodes\n";
}

my @edges;

my %nodenames;
my %namenodes;
my %breeds;

while(my $addedge = shift(@addedges)) {
  my @extranodes;

  foreach my $node (@nodes) {
    my $end1 = $node->{'who'};

    my $nodelinks = $$links{$end1};

    foreach my $end2 (keys(%$nodelinks)) {
      
      foreach my $link (@{$$links{$end1}->{$end2}}) {
	if($link->{'breed'} eq '{breed '.$addedge.'}') {
	  $breeds{$link->{'breed'}} = $addedge;

	  push(@edges, $link);

	  $nodenames{$link->{'end1'}} = $end1;
	  $nodenames{$link->{'end2'}} = $end2;

	  $namenodes{$end1} = {} if(!defined($namenodes{$end1}));
	  $namenodes{$end2} = {} if(!defined($namenodes{$end2}));

	  $namenodes{$end1}->{$link->{'end1'}} = 1;
	  $namenodes{$end2}->{$link->{'end2'}} = 1;

	  push(@extranodes, $turtles->{$end2});
	}
      }

    }
  }
   
  push(@nodes, @extranodes);
}

if(scalar(@edges) == 0) {
  die "Got no edges\n";
}

open(DOT, ">$dotfile") or die "Cannot create DOT file $dotfile: $!\n";

print DOT 'digraph G {', "\n";

my %nlogostdlinkheadings = ('end1' => 0,
			    'end2' => 1,
			    'color' => 2,
			    'label' => 3,
			    'label-color' => 4,
			    'hidden?' => 5,
			    'breed' => 6,
			    'thickness' => 7,
			    'shape' => 8,
			    'tie-mode' => 9,
			    'broken?' => 10);

foreach my $edge (@edges) {
  print DOT "  ";

  my $end1 = $nodenames{$edge->{'end1'}};
  my $end2 = $nodenames{$edge->{'end2'}};

  print DOT "turtle$end1 -> turtle$end2";

  my $breed = $breeds{$edge->{'breed'}};

  my @linkvalues;
  foreach my $key (keys(%$edge)) {
    if(!defined($nlogostdlinkheadings{$key})) {
      push(@linkvalues, "\\n".$key." = ".$edge->{$key})
	if $edge->{$key} =~ /\S/ and $edge->{$key} ne '""'
	and $edge->{$key} !~ /\{/ and $edge->{$key} !~ /\[/;
    }
  }

  if(scalar(@addedges) > 1) {
    my $linklabel = $breed;

    if($data && scalar(@linkvalues) > 0) {
      $linklabel .= ":";
      foreach my $linkvalue (@linkvalues) {
	$linklabel .= $linkvalue;
      }
    }

    $linklabel =~ s/\"//g;

    print DOT " [label = \"$linklabel\"]";
  }
  elsif($data && scalar(@linkvalues) > 0) {
    my $linklabel = join("", @linkvalues);
    $linklabel = substr($linklabel, 2);
    $linklabel =~ s/\"//g;

    print DOT " [label = \"$linklabel\"]";
  }

  print DOT ";\n";
}

my %nlogostdturtleheadings = ("who" => 0,
			      "color" => 1,
			      "heading" => 2,
			      "xcor" => 3,
			      "ycor" => 4,
			      "shape" => 5,
			      "label" => 6,
			      "label-color" => 7,
			      "breed" => 8,
			      "hidden?" => 9,
			      "size" => 10,
			      "pen-size" => 11,
			      "pen-mode" => 12);

foreach my $node (@nodes) {
  print DOT "  turtle$node->{'who'}";

  my $label = defined($namenodes{$node->{'who'}})
    ? join("\\n", keys(%{$namenodes{$node->{'who'}}}))
    : $node->{'who'};

  if(defined($nodelabels{$node->{'breed'}})) {
    $label = $node->{$nodelabels{$node->{'breed'}}};
  }

  if($data) {
    my @nodevalues;

    my $shape = 'box';

    foreach my $key (keys(%$node)) {
      if(!defined($nlogostdturtleheadings{$key})) {
	if($node->{$key} =~ /\S/ && $node->{$key} ne '""'
	   && $node->{$key} !~ /\{/ && $node->{$key} !~ /\[/) {
	  $label .= "|{$key|$node->{$key}}";
	  $shape = 'record';
	}
      }      
    }

    $label =~ s/\"//g;

    print DOT " [label = \"$label\", shape = $shape]";
  }
  else {
    print DOT " [label = \"$label\"]";
  }

  print DOT ";\n";
}

print DOT '}', "\n";

close(DOT);

exit 0;


