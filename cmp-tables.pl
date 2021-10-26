#!/usr/bin/perl

use strict;

use nlogo2R;

my %param;
my %first_param;
my $first = 1;
my %other_param;

foreach my $file (@ARGV) {
  my ($headers, $data) = nlogo2R::readfile($file, 0);

  if($first) {
    $first = 0;
    foreach my $header (@$headers) {
      next if $header eq 'run';
      last if $header eq 'step';
      $first_param{$header} = 1;
    }
  }

  for(my $i = 1; $i <= $#$headers && $$headers[$i] ne "step"; $i++) {
    $param{$$headers[$i]}->{$$data[$i]}++;

    if(!$first && !defined($first_param{$$headers[$i]})) {
      $other_param{$header} = 1;
    }
  }
}

print "Single parameter settings\nParameter,Value\n";
foreach my $parm (sort { $a cmp $b } keys(%param)) {
  if(!defined($other_param{$parm})) {
    my $valuet = $param{$parm};

    if(scalar(keys(%$valuet)) == 1) {
      print $parm, ",", join(",", keys(%$valuet)), "\n";
    }
  }
}
print "Single parameter settings (not in all files)\nParameter,Value,N\n";
foreach my $parm (sort { $a cmp $b } keys(%param)) {
  if(defined($other_param{$parm})) {
    my $valuet = $param{$parm};

    if(scalar(keys(%$valuet)) == 1) {
      print $parm, ",", join(",", keys(%$valuet)), ",", join(",", values(%$valuet)), "\n";
    }
  }
}
print "Multiple settings\nParameter,Value1,N1,...\n";
foreach my $parm (sort { $a cmp $b } keys(%param)) {
  if(!defined($other_param{$parm})) {
    my $valuet = $param{$parm};

    print "$parm";
    foreach my $value (sort { $a cmp $b } keys(%$valuet)) {
      print ",$value,$$valuet{$value}";
    }
    print "\n";
  }
}
print "Multiple settings (not in all files)\nParameter,Value1,N1,...\n";
foreach my $parm (sort { $a cmp $b } keys(%param)) {
  if(defined($other_param{$parm})) {
    my $valuet = $param{$parm};

    print "$parm";
    foreach my $value (sort { $a cmp $b } keys(%$valuet)) {
      print ",$value,$$valuet{$value}";
    }
    print "\n";
  }
}
